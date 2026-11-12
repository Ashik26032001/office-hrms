"""
Core attendance service.
Handles QR scan, Face scan, Fingerprint scan — all with optional geofence check.
"""
from django.utils import timezone
from django.db import transaction
from .models import AttendanceEvent
from .geofence import check_geofence
from employees.models import Employee


# ─── SHARED HELPERS ───────────────────────────────────────────────────────────

def get_live_status(employee, date=None):
    if date is None:
        date = timezone.localdate()
    last = AttendanceEvent.objects.filter(
        employee=employee, timestamp__date=date
    ).order_by('-timestamp').first()
    return last.event_type if last else 'OUT'


def _build_response(employee, event_type, method):
    """Build the standard success response dict."""
    now = timezone.now()
    return {
        'employee_id': employee.employee_id,
        'name':        employee.get_full_name(),
        'department':  employee.department.name if employee.department else '',
        'action':      event_type,
        'method':      method,
        'timestamp':   timezone.localtime(now).strftime('%I:%M:%S %p'),
        'date':        timezone.localdate().strftime('%d %b %Y'),
        'photo_url':   employee.photo.url if employee.photo else None,
    }


@transaction.atomic
def _record_event(employee, event_type, method, lat=None, lon=None,
                  geo_result=None, scanner_note=None):
    """Create AttendanceEvent. Shared by all three scan methods."""
    note = scanner_note or f'{method.upper()} Scanner'
    event = AttendanceEvent.objects.create(
        employee        = employee,
        event_type      = event_type,
        method          = method,
        scanner_note    = note,
        scan_latitude   = lat,
        scan_longitude  = lon,
        location_valid  = geo_result['is_valid'] if geo_result else None,
        distance_metres = geo_result['distance']  if geo_result else None,
    )
    return event


def _prevent_duplicate(employee):
    """Raise if scanned within last 10 seconds."""
    now = timezone.now()
    recent = AttendanceEvent.objects.filter(
        employee=employee,
        timestamp__gte=now - timezone.timedelta(seconds=10)
    ).exists()
    if recent:
        raise ValueError('Duplicate scan detected. Please wait a moment.')


# ─── 1. QR SCAN ───────────────────────────────────────────────────────────────

@transaction.atomic
def process_qr_scan(qr_token, lat=None, lon=None):
    """
    Process a QR code scan with optional geofence check.
    lat/lon: float GPS coords from browser (None = geofence skipped)
    """
    try:
        employee = Employee.objects.select_related('user', 'department').get(
            qr_token=qr_token, status='active'
        )
    except Employee.DoesNotExist:
        raise ValueError('Invalid or inactive employee QR code.')

    _prevent_duplicate(employee)

    geo_result = None
    if lat is not None and lon is not None:
        geo_result = check_geofence(lat, lon)
        if not geo_result['is_valid']:
            raise ValueError(geo_result['message'])

    today      = timezone.localdate()
    event_type = 'OUT' if get_live_status(employee, today) == 'IN' else 'IN'
    _record_event(employee, event_type, 'qr', lat, lon, geo_result)

    result = _build_response(employee, event_type, 'QR Scan')
    if geo_result:
        result['location_message'] = geo_result['message']
        result['distance']         = geo_result['distance']
    return result


# ─── 2. FACE RECOGNITION SCAN ─────────────────────────────────────────────────

@transaction.atomic
def process_face_scan(captured_b64, lat=None, lon=None):
    """
    Process a face recognition scan.
    captured_b64: base64 JPEG from browser webcam canvas.
    """
    from .face_service import find_matching_employee

    geo_result = None
    if lat is not None and lon is not None:
        geo_result = check_geofence(lat, lon)
        if not geo_result['is_valid']:
            raise ValueError(geo_result['message'])

    employee, face_info = find_matching_employee(captured_b64)

    if employee is None:
        raise ValueError(face_info.get('error', 'Face not recognised. Please try again.'))

    _prevent_duplicate(employee)

    today      = timezone.localdate()
    event_type = 'OUT' if get_live_status(employee, today) == 'IN' else 'IN'

    note = (f"Face Recognition | model={face_info.get('model','')} "
            f"distance={face_info.get('distance','')}")
    _record_event(employee, event_type, 'face', lat, lon, geo_result, note)

    result = _build_response(employee, event_type, 'Face Recognition')
    result['face_distance'] = face_info.get('distance')
    if geo_result:
        result['location_message'] = geo_result['message']
    return result


# ─── 3. FINGERPRINT / WEBAUTHN SCAN ───────────────────────────────────────────

@transaction.atomic
def process_fingerprint_scan(employee_id, assertion_json, lat=None, lon=None):
    """
    Process a WebAuthn fingerprint authentication.
    employee_id: the employee's DB pk (passed from browser)
    assertion_json: dict from browser navigator.credentials.get()
    """
    from .webauthn_service import verify_authentication

    try:
        employee = Employee.objects.select_related('user', 'department').get(
            pk=employee_id, status='active', webauthn_enrolled=True
        )
    except Employee.DoesNotExist:
        raise ValueError('Employee not found or fingerprint not enrolled.')

    geo_result = None
    if lat is not None and lon is not None:
        geo_result = check_geofence(lat, lon)
        if not geo_result['is_valid']:
            raise ValueError(geo_result['message'])

    ok, message = verify_authentication(employee, assertion_json)
    if not ok:
        raise ValueError(f'Fingerprint verification failed: {message}')

    _prevent_duplicate(employee)

    today      = timezone.localdate()
    event_type = 'OUT' if get_live_status(employee, today) == 'IN' else 'IN'
    _record_event(employee, event_type, 'fingerprint', lat, lon, geo_result)

    result = _build_response(employee, event_type, 'Fingerprint')
    if geo_result:
        result['location_message'] = geo_result['message']
    return result


# ─── SHARED UTILS ─────────────────────────────────────────────────────────────

def calculate_working_hours(employee, date):
    events = list(AttendanceEvent.objects.filter(
        employee=employee, timestamp__date=date
    ).order_by('timestamp'))

    total_minutes = 0
    sessions = []
    i = 0
    while i < len(events):
        if events[i].event_type == 'IN':
            in_event = events[i]
            if i + 1 < len(events) and events[i + 1].event_type == 'OUT':
                out_event = events[i + 1]
                diff = int((out_event.timestamp - in_event.timestamp).total_seconds() // 60)
                total_minutes += diff
                sessions.append({
                    'in_time':  timezone.localtime(in_event.timestamp),
                    'out_time': timezone.localtime(out_event.timestamp),
                    'minutes':  diff,
                    'hours':    diff // 60,
                    'mins':     diff % 60,
                })
                i += 2
                continue
            else:
                sessions.append({
                    'in_time':  timezone.localtime(in_event.timestamp),
                    'out_time': None,
                    'minutes':  None,
                    'hours':    None,
                    'mins':     None,
                })
        i += 1

    return {
        'sessions':      sessions,
        'total_minutes': total_minutes,
        'hours':         total_minutes // 60,
        'minutes':       total_minutes % 60,
    }


def get_all_today_status():
    today = timezone.localdate()
    employees = Employee.objects.filter(status='active').select_related('user', 'department')
    result = []
    for emp in employees:
        last_event  = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=today
        ).order_by('-timestamp').first()
        first_in    = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=today, event_type='IN'
        ).order_by('timestamp').first()
        last_out    = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=today, event_type='OUT'
        ).order_by('-timestamp').first()
        wh   = calculate_working_hours(emp, today)
        live = last_event.event_type if last_event else 'OUT'
        result.append({
            'employee':      emp,
            'live_status':   live,
            'first_in':      timezone.localtime(first_in.timestamp) if first_in else None,
            'last_out':      timezone.localtime(last_out.timestamp)  if last_out else None,
            'total_hours':   wh['hours'],
            'total_minutes': wh['minutes'],
            'is_present':    last_event is not None,
        })
    return result
