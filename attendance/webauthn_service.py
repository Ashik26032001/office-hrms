"""
WebAuthn service — supports multiple finger credentials per employee.
Each employee can enroll up to max_fingers_allowed fingers (default 3).
Admin controls max_fingers_allowed per employee.
"""
import base64
import json
import secrets
import struct
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)


def generate_challenge() -> str:
    return b64url_encode(secrets.token_bytes(32))


# ─── REGISTRATION ─────────────────────────────────────────────────────────────

def get_registration_options(employee, finger_label='any'):
    """
    Build registration options for one finger.
    Returns error if employee already has max fingers enrolled.
    """
    from employees.models import FingerCredential
    from attendance.models import WebAuthnChallenge

    # Check finger limit
    current_count = FingerCredential.objects.filter(
        employee=employee, is_active=True
    ).count()

    if current_count >= employee.max_fingers_allowed:
        raise ValueError(
            f"Maximum {employee.max_fingers_allowed} finger(s) already enrolled. "
            f"Ask admin to increase the limit or delete an existing finger."
        )

    rp_id   = getattr(settings, 'WEBAUTHN_RP_ID',   '127.0.0.1')
    rp_name = getattr(settings, 'WEBAUTHN_RP_NAME', 'SmartHR')

    challenge = generate_challenge()

    # Store challenge
    WebAuthnChallenge.objects.filter(
        employee=employee, purpose='register'
    ).delete()
    WebAuthnChallenge.objects.create(
        employee=employee, challenge=challenge, purpose='register'
    )

    # Exclude already-enrolled credentials so device doesn't duplicate
    existing = list(FingerCredential.objects.filter(
        employee=employee, is_active=True
    ).values_list('credential_id', flat=True))

    user_id = b64url_encode(str(employee.pk).encode())

    options = {
        'rp': {'id': rp_id, 'name': rp_name},
        'user': {
            'id':          user_id,
            'name':        employee.user.username,
            'displayName': employee.get_full_name(),
        },
        'challenge':       challenge,
        'pubKeyCredParams': [
            {'type': 'public-key', 'alg': -7},
            {'type': 'public-key', 'alg': -257},
        ],
        'timeout':          60000,
        'excludeCredentials': [
            {'type': 'public-key', 'id': cid} for cid in existing
        ],
        'authenticatorSelection': {
            'authenticatorAttachment': 'platform',
            'userVerification':        'required',
            'residentKey':             'preferred',
        },
        'attestation':  'none',
        'finger_label': finger_label,  # passed back to client for reference
        'current_count':     current_count,
        'max_allowed':       employee.max_fingers_allowed,
    }
    return options


def verify_registration(employee, credential_json, finger_label='any', device_info=''):
    """Verify and save one finger credential."""
    try:
        from employees.models import FingerCredential
        from attendance.models import WebAuthnChallenge

        ch_obj = WebAuthnChallenge.objects.filter(
            employee=employee, purpose='register'
        ).latest('created_at')

        if ch_obj.is_expired():
            ch_obj.delete()
            return False, 'Challenge expired. Please try again.'

        expected_challenge = ch_obj.challenge

        client_data = json.loads(
            b64url_decode(credential_json.get('clientDataJSON', '')).decode()
        )

        if client_data.get('type') != 'webauthn.create':
            return False, 'Invalid credential type.'

        if client_data.get('challenge', '') != expected_challenge:
            return False, 'Challenge mismatch.'

        credential_id = credential_json.get('id', '')
        public_key    = credential_json.get('response', {}).get('attestationObject', '')

        if not credential_id or not public_key:
            return False, 'Missing credential data.'

        # Save as a FingerCredential
        FingerCredential.objects.create(
            employee     = employee,
            finger_label = finger_label,
            credential_id = credential_id,
            public_key    = public_key,
            sign_count    = 0,
            device_info   = device_info or '',
        )

        # Update legacy field for backward compatibility
        employee.webauthn_enrolled      = True
        employee.webauthn_credential_id = credential_id
        employee.webauthn_public_key    = public_key
        employee.save(update_fields=[
            'webauthn_enrolled', 'webauthn_credential_id', 'webauthn_public_key'
        ])

        ch_obj.delete()

        count = FingerCredential.objects.filter(employee=employee, is_active=True).count()
        logger.info(f"Finger enrolled: {employee.employee_id} ({finger_label}) — total {count}")
        return True, f'Finger enrolled! ({count}/{employee.max_fingers_allowed} used)'

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return False, f'Enrollment failed: {str(e)}'


# ─── AUTHENTICATION ────────────────────────────────────────────────────────────

def get_authentication_options(employee):
    """
    Build auth options listing ALL enrolled fingers for this employee.
    Browser will match whichever credential is on the device.
    """
    from employees.models import FingerCredential
    from attendance.models import WebAuthnChallenge

    credentials = FingerCredential.objects.filter(
        employee=employee, is_active=True
    )

    if not credentials.exists():
        raise ValueError('No fingerprints enrolled. Please enroll first.')

    rp_id     = getattr(settings, 'WEBAUTHN_RP_ID', '127.0.0.1')
    challenge = generate_challenge()

    WebAuthnChallenge.objects.filter(
        employee=employee, purpose='authenticate'
    ).delete()
    WebAuthnChallenge.objects.create(
        employee=employee, challenge=challenge, purpose='authenticate'
    )

    options = {
        'challenge':         challenge,
        'rpId':              rp_id,
        'timeout':           60000,
        'userVerification':  'required',
        'allowCredentials': [
            {
                'type':       'public-key',
                'id':         c.credential_id,
                'transports': ['internal'],
            }
            for c in credentials
        ],
    }
    return options


def verify_authentication(employee, assertion_json):
    """Verify assertion against any of the employee's enrolled fingers."""
    try:
        from employees.models import FingerCredential
        from attendance.models import WebAuthnChallenge
        from django.utils import timezone

        ch_obj = WebAuthnChallenge.objects.filter(
            employee=employee, purpose='authenticate'
        ).latest('created_at')

        if ch_obj.is_expired():
            ch_obj.delete()
            return False, 'Challenge expired. Please scan again.'

        expected_challenge = ch_obj.challenge
        received_id        = assertion_json.get('id', '')

        # Find matching credential
        try:
            finger = FingerCredential.objects.get(
                employee=employee,
                credential_id=received_id,
                is_active=True,
            )
        except FingerCredential.DoesNotExist:
            return False, 'Fingerprint not recognised. Please try another finger.'

        # Verify challenge
        client_data = json.loads(
            b64url_decode(assertion_json.get('clientDataJSON', '')).decode()
        )
        if client_data.get('type') != 'webauthn.get':
            return False, 'Invalid assertion type.'
        if client_data.get('challenge', '') != expected_challenge:
            return False, 'Challenge mismatch.'

        # Update sign count (anti-replay)
        auth_data_b64 = assertion_json.get('authenticatorData', '')
        if auth_data_b64:
            auth_data = b64url_decode(auth_data_b64)
            if len(auth_data) >= 37:
                new_count = struct.unpack('>I', auth_data[33:37])[0]
                if new_count > 0 and new_count <= finger.sign_count:
                    return False, 'Sign count invalid. Possible cloned authenticator.'
                finger.sign_count  = new_count
                finger.last_used_at = timezone.now()
                finger.save(update_fields=['sign_count', 'last_used_at'])

        ch_obj.delete()
        logger.info(f"Fingerprint verified: {employee.employee_id} ({finger.finger_label})")
        return True, f'Fingerprint verified ({finger.get_finger_label_display()})'

    except Exception as e:
        logger.error(f"Auth error: {e}")
        return False, f'Authentication failed: {str(e)}'
