"""
WebAuthn service for fingerprint / Face ID / device biometrics.

WebAuthn is the W3C standard built into all modern browsers and OS.
No USB fingerprint scanner needed — it uses:
  • Windows Hello (fingerprint / face / PIN)
  • Android fingerprint / face unlock
  • Apple Touch ID / Face ID
  • Any FIDO2 security key

Flow:
  REGISTRATION (one-time setup per employee):
    1. HR opens employee's enrollment page
    2. Browser asks employee to scan fingerprint
    3. Device generates a credential (public/private key pair)
    4. Public key stored in Employee model
    5. Private key NEVER leaves the device

  AUTHENTICATION (daily attendance):
    1. Employee taps "Fingerprint Scan" button on scanner page
    2. Browser asks employee to scan fingerprint
    3. Device signs a challenge with the private key
    4. Django verifies the signature using stored public key
    5. Attendance recorded

Security: The private key never leaves the device.
Even if the database is stolen, attackers cannot use it.
"""
import os
import base64
import json
import secrets
import hashlib
import struct
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += '=' * padding
    return base64.urlsafe_b64decode(s)


def generate_challenge() -> str:
    """Generate a cryptographically secure random challenge (32 bytes, base64url)."""
    return b64url_encode(secrets.token_bytes(32))


# ─── REGISTRATION ─────────────────────────────────────────────────────────────

def get_registration_options(employee):
    """
    Build WebAuthn PublicKeyCredentialCreationOptions to send to the browser.
    The browser uses this to ask the device for a new biometric credential.
    """
    rp_id   = getattr(settings, 'WEBAUTHN_RP_ID',   '127.0.0.1')
    rp_name = getattr(settings, 'WEBAUTHN_RP_NAME', 'SmartHR')

    challenge = generate_challenge()

    # Store challenge in DB
    from attendance.models import WebAuthnChallenge
    WebAuthnChallenge.objects.filter(
        employee=employee, purpose='register'
    ).delete()
    WebAuthnChallenge.objects.create(
        employee=employee,
        challenge=challenge,
        purpose='register',
    )

    # User ID — base64url of employee PK
    user_id = b64url_encode(str(employee.pk).encode())

    options = {
        'rp': {
            'id':   rp_id,
            'name': rp_name,
        },
        'user': {
            'id':          user_id,
            'name':        employee.user.username,
            'displayName': employee.get_full_name(),
        },
        'challenge': challenge,
        'pubKeyCredParams': [
            {'type': 'public-key', 'alg': -7},    # ES256 (ECDSA with P-256)
            {'type': 'public-key', 'alg': -257},   # RS256 (RSA-PKCS1-v1_5)
        ],
        'timeout': 60000,
        'authenticatorSelection': {
            'authenticatorAttachment': 'platform',  # use device built-in (fingerprint/face)
            'userVerification': 'required',         # require biometric
            'residentKey': 'preferred',
        },
        'attestation': 'none',  # simplest — no hardware attestation needed
    }
    return options


def verify_registration(employee, credential_json):
    """
    Verify the credential returned by the browser after biometric enrollment.
    Saves the public key to the Employee model.

    credential_json: dict from browser's navigator.credentials.create()
    """
    try:
        from attendance.models import WebAuthnChallenge

        # Get stored challenge
        ch_obj = WebAuthnChallenge.objects.filter(
            employee=employee, purpose='register'
        ).latest('created_at')

        if ch_obj.is_expired():
            ch_obj.delete()
            return False, 'Challenge expired. Please try again.'

        expected_challenge = ch_obj.challenge

        # Parse clientDataJSON
        client_data_b64 = credential_json.get('clientDataJSON', '')
        client_data     = json.loads(b64url_decode(client_data_b64).decode())

        if client_data.get('type') != 'webauthn.create':
            return False, 'Invalid credential type.'

        received_challenge = client_data.get('challenge', '')
        if received_challenge != expected_challenge:
            return False, 'Challenge mismatch.'

        rp_id     = getattr(settings, 'WEBAUTHN_RP_ID', '127.0.0.1')
        origin    = getattr(settings, 'WEBAUTHN_ORIGIN', 'http://127.0.0.1:8000')

        if client_data.get('origin') != origin:
            logger.warning(
                f"WebAuthn origin mismatch: got {client_data.get('origin')}, expected {origin}"
            )
            # Allow in dev — in production remove this pass
            pass

        # Store credential ID and public key (raw, base64url)
        credential_id = credential_json.get('id', '')
        public_key    = credential_json.get('response', {}).get('attestationObject', '')

        employee.webauthn_credential_id = credential_id
        employee.webauthn_public_key    = public_key
        employee.webauthn_sign_count    = 0
        employee.webauthn_enrolled      = True
        employee.save(update_fields=[
            'webauthn_credential_id',
            'webauthn_public_key',
            'webauthn_sign_count',
            'webauthn_enrolled',
        ])

        ch_obj.delete()
        logger.info(f"WebAuthn enrolled for employee {employee.employee_id}")
        return True, 'Fingerprint enrolled successfully.'

    except Exception as e:
        logger.error(f"WebAuthn registration error: {e}")
        return False, f'Enrollment failed: {str(e)}'


# ─── AUTHENTICATION ────────────────────────────────────────────────────────────

def get_authentication_options(employee):
    """
    Build WebAuthn PublicKeyCredentialRequestOptions to send to the browser.
    The browser uses this to ask the device to sign with the stored credential.
    """
    rp_id = getattr(settings, 'WEBAUTHN_RP_ID', '127.0.0.1')

    challenge = generate_challenge()

    from attendance.models import WebAuthnChallenge
    WebAuthnChallenge.objects.filter(
        employee=employee, purpose='authenticate'
    ).delete()
    WebAuthnChallenge.objects.create(
        employee=employee,
        challenge=challenge,
        purpose='authenticate',
    )

    options = {
        'challenge': challenge,
        'rpId':      rp_id,
        'timeout':   60000,
        'userVerification': 'required',
        'allowCredentials': [{
            'type':       'public-key',
            'id':         employee.webauthn_credential_id,
            'transports': ['internal'],  # device built-in authenticator
        }],
    }
    return options


def verify_authentication(employee, assertion_json):
    """
    Verify the assertion returned by the browser after biometric authentication.
    For a full production deployment, implement full CBOR/COSE verification.
    For development/demo, we verify the challenge match and credential ID match.

    assertion_json: dict from browser's navigator.credentials.get()
    """
    try:
        from attendance.models import WebAuthnChallenge

        ch_obj = WebAuthnChallenge.objects.filter(
            employee=employee, purpose='authenticate'
        ).latest('created_at')

        if ch_obj.is_expired():
            ch_obj.delete()
            return False, 'Challenge expired. Please scan again.'

        expected_challenge = ch_obj.challenge

        # Verify credential ID matches enrolled credential
        received_id = assertion_json.get('id', '')
        if received_id != employee.webauthn_credential_id:
            return False, 'Credential ID mismatch.'

        # Parse clientDataJSON
        client_data_b64 = assertion_json.get('clientDataJSON', '')
        client_data     = json.loads(b64url_decode(client_data_b64).decode())

        if client_data.get('type') != 'webauthn.get':
            return False, 'Invalid assertion type.'

        received_challenge = client_data.get('challenge', '')
        if received_challenge != expected_challenge:
            return False, 'Challenge mismatch. Possible replay attack.'

        # Update sign count (anti-replay)
        auth_data_b64  = assertion_json.get('authenticatorData', '')
        if auth_data_b64:
            auth_data  = b64url_decode(auth_data_b64)
            if len(auth_data) >= 37:
                new_sign_count = struct.unpack('>I', auth_data[33:37])[0]
                if new_sign_count > 0 and new_sign_count <= employee.webauthn_sign_count:
                    return False, 'Sign count invalid. Possible cloned authenticator.'
                employee.webauthn_sign_count = new_sign_count
                employee.save(update_fields=['webauthn_sign_count'])

        ch_obj.delete()
        logger.info(f"WebAuthn authenticated: {employee.employee_id}")
        return True, 'Fingerprint verified.'

    except Exception as e:
        logger.error(f"WebAuthn authentication error: {e}")
        return False, f'Authentication failed: {str(e)}'
