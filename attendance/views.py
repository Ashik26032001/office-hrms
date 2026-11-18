import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from .models import AttendanceEvent
from .services import (
    process_qr_scan, process_face_scan, process_fingerprint_scan,
    get_all_today_status, calculate_working_hours
)
from .webauthn_service import (
    get_registration_options, verify_registration,
    get_authentication_options
)
from employees.models import Employee


def hr_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        if not request.user.is_admin_or_hr():
            return redirect('/employee/dashboard/')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCANNER PAGE (all three methods)
# ─────────────────────────────────────────────────────────────────────────────

@hr_required
def office_scanner(request):
    today = timezone.localdate()
    recent_scans = AttendanceEvent.objects.filter(
        timestamp__date=today
    ).select_related('employee__user', 'employee__department').order_by('-timestamp')[:8]

    enrolled_employees = Employee.objects.filter(
        status='active', face_enrolled=True
    ).count()
    fp_enrolled = Employee.objects.filter(
        status='active', webauthn_enrolled=True
    ).count()
    total_active = Employee.objects.filter(status='active').count()

    # Read from DB settings (set via Settings page)
    from attendance.geofence import get_office_config
    office_lat, office_lon, geo_radius, geo_enabled = get_office_config()

    return render(request, 'attendance/office_scanner.html', {
        'recent_scans':      recent_scans,
        'today':             today,
        'face_enrolled':     enrolled_employees,
        'fp_enrolled':       fp_enrolled,
        'total_active':      total_active,
        'office_lat':        office_lat,
        'office_lon':        office_lon,
        'geo_radius':        geo_radius,
    })


# ─────────────────────────────────────────────────────────────────────────────
# QR SCAN API
# ─────────────────────────────────────────────────────────────────────────────

@require_POST
def scan_qr_api(request):
    try:
        body      = json.loads(request.body)
        qr_token  = body.get('qr_token', '').strip()
        lat       = body.get('latitude')
        lon       = body.get('longitude')
        if not qr_token:
            return JsonResponse({'success': False, 'message': 'No QR data received.'}, status=400)

        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None

        result = process_qr_scan(qr_token, lat, lon)
        return JsonResponse({'success': True, **result})

    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Server error. Try again.'}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# FACE RECOGNITION API
# ─────────────────────────────────────────────────────────────────────────────

@require_POST
def face_scan_api(request):
    """Receives base64 webcam frame, runs face recognition, records attendance."""
    try:
        body          = json.loads(request.body)
        captured_b64  = body.get('image', '').strip()
        lat           = body.get('latitude')
        lon           = body.get('longitude')

        if not captured_b64:
            return JsonResponse({'success': False, 'message': 'No image received.'}, status=400)

        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None

        result = process_face_scan(captured_b64, lat, lon)
        return JsonResponse({'success': True, **result})

    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Face scan error: {str(e)}'}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# FINGERPRINT / WEBAUTHN APIs
# ─────────────────────────────────────────────────────────────────────────────

@require_POST
def webauthn_auth_options(request):
    """Return WebAuthn challenge options for fingerprint authentication."""
    try:
        body        = json.loads(request.body)
        employee_id = body.get('employee_id')
        employee    = Employee.objects.get(pk=employee_id, status='active', webauthn_enrolled=True)
        options     = get_authentication_options(employee)
        return JsonResponse({'success': True, 'options': options})
    except Employee.DoesNotExist:
        return JsonResponse(
            {'success': False, 'message': 'Employee not found or fingerprint not enrolled.'},
            status=400
        )
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@require_POST
def fingerprint_scan_api(request):
    """Verify WebAuthn assertion and record attendance."""
    try:
        body          = json.loads(request.body)
        employee_id   = body.get('employee_id')
        assertion     = body.get('assertion', {})
        lat           = body.get('latitude')
        lon           = body.get('longitude')

        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None

        result = process_fingerprint_scan(employee_id, assertion, lat, lon)
        return JsonResponse({'success': True, **result})

    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# WEBAUTHN REGISTRATION (HR enrolls employee fingerprint)
# ─────────────────────────────────────────────────────────────────────────────

@hr_required
def webauthn_register_options(request, pk):
    """Return registration options so employee can enroll one finger."""
    try:
        employee     = get_object_or_404(Employee, pk=pk)
        finger_label = request.GET.get('finger', 'any')
        options      = get_registration_options(employee, finger_label)
        return JsonResponse({'success': True, 'options': options})
    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@require_POST
@hr_required
def webauthn_register_verify(request, pk):
    """Verify registration credential and save finger."""
    try:
        employee     = get_object_or_404(Employee, pk=pk)
        body         = json.loads(request.body)
        finger_label = body.get('finger_label', 'any')
        device_info  = body.get('device_info', '')
        ok, msg      = verify_registration(employee, body, finger_label, device_info)
        if ok:
            return JsonResponse({'success': True, 'message': msg})
        return JsonResponse({'success': False, 'message': msg}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# GEOFENCE CHECK API (standalone — used by scanner to preview location)
# ─────────────────────────────────────────────────────────────────────────────

def geofence_check_api(request):
    """Preview: check if given coords are inside the office geofence."""
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    if not lat or not lon:
        return JsonResponse({'success': False, 'message': 'lat/lon required.'}, status=400)
    try:
        from .geofence import check_geofence
        result = check_geofence(float(lat), float(lon))
        return JsonResponse({'success': True, **result})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# FACE ENROLLMENT (HR uploads/takes employee face photo)
# ─────────────────────────────────────────────────────────────────────────────

@hr_required
def enroll_face(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        # Accept either file upload or base64 from webcam
        if 'face_photo' in request.FILES:
            employee.face_photo   = request.FILES['face_photo']
            employee.face_enrolled = True
            employee.save(update_fields=['face_photo', 'face_enrolled'])
            messages.success(request, f"Face photo enrolled for {employee.get_full_name()}.")
        elif request.content_type == 'application/json':
            try:
                body    = json.loads(request.body)
                b64_img = body.get('image', '')
                if b64_img:
                    import base64, io
                    from django.core.files.base import ContentFile
                    if ',' in b64_img:
                        b64_img = b64_img.split(',', 1)[1]
                    image_data = base64.b64decode(b64_img)
                    fname      = f"face_{employee.employee_id}.jpg"
                    employee.face_photo.save(fname, ContentFile(image_data), save=False)
                    employee.face_enrolled = True
                    employee.save(update_fields=['face_photo', 'face_enrolled'])
                    return JsonResponse({'success': True, 'message': 'Face enrolled.'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
        return redirect('employee_detail', pk=pk)

    return render(request, 'attendance/enroll_face.html', {'emp': employee})


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING VIEWS (attendance log, history, manual, live API)
# ─────────────────────────────────────────────────────────────────────────────

@hr_required
def attendance_log(request):
    date_str   = request.GET.get('date', timezone.localdate().isoformat())
    emp_filter = request.GET.get('emp', '')
    try:
        from datetime import date as dtdate
        filter_date = dtdate.fromisoformat(date_str)
    except (ValueError, TypeError):
        filter_date = timezone.localdate()

    events = AttendanceEvent.objects.filter(
        timestamp__date=filter_date
    ).select_related('employee__user', 'employee__department').order_by('-timestamp')

    if emp_filter:
        from django.db.models import Q
        events = events.filter(
            Q(employee__employee_id__icontains=emp_filter) |
            Q(employee__user__first_name__icontains=emp_filter) |
            Q(employee__user__last_name__icontains=emp_filter)
        )

    all_today_status = get_all_today_status()
    total_employees  = Employee.objects.filter(status='active').count()
    present_count    = sum(1 for e in all_today_status if e['is_present'])
    in_count         = sum(1 for e in all_today_status if e['live_status'] == 'IN')
    absent_count     = max(0, total_employees - present_count)

    context = {
        'events':           events,
        'filter_date':      filter_date,
        'emp_filter':       emp_filter,
        'all_today_status': all_today_status,
        'present_count':    present_count,
        'in_count':         in_count,
        'absent_count':     absent_count,
        'total_employees':  total_employees,
    }
    return render(request, 'attendance/attendance_log.html', context)


@hr_required
def employee_attendance_history(request, pk):
    emp   = get_object_or_404(Employee.objects.select_related('user', 'department'), pk=pk)
    month = request.GET.get('month', timezone.localdate().month)
    year  = request.GET.get('year',  timezone.localdate().year)

    events = AttendanceEvent.objects.filter(
        employee=emp, timestamp__month=month, timestamp__year=year,
    ).order_by('timestamp')

    from django.utils.timezone import localtime
    grouped = {}
    for ev in events:
        d = localtime(ev.timestamp).date()
        grouped.setdefault(d, []).append(ev)

    day_data = []
    for d, evs in sorted(grouped.items()):
        wh = calculate_working_hours(emp, d)
        day_data.append({
            'date':          d,
            'events':        evs,
            'total_hours':   wh['hours'],
            'total_minutes': wh['minutes'],
            'sessions':      wh['sessions'],
        })

    total_working_minutes = sum(
        e['total_hours'] * 60 + e['total_minutes'] for e in day_data
    )
    context = {
        'emp':                   emp,
        'day_data':              day_data,
        'month':                 int(month),
        'year':                  int(year),
        'total_days':            len(day_data),
        'total_working_minutes': total_working_minutes,
        'total_hours':           total_working_minutes // 60,
        'total_mins':            total_working_minutes % 60,
    }
    return render(request, 'attendance/employee_history.html', context)


@hr_required
def manual_attendance(request):
    employees = Employee.objects.filter(status='active').select_related('user')
    if request.method == 'POST':
        emp_id       = request.POST.get('employee')
        event_type   = request.POST.get('event_type')
        timestamp_str = request.POST.get('timestamp')
        try:
            emp = Employee.objects.get(pk=emp_id)
            from datetime import datetime
            ts  = timezone.make_aware(datetime.fromisoformat(timestamp_str))
            AttendanceEvent.objects.create(
                employee     = emp,
                event_type   = event_type,
                method       = 'manual',
                timestamp    = ts,
                is_manual    = True,
                scanner_note = 'Manual Entry by Admin',
            )
            messages.success(request, f"Manual {event_type} recorded for {emp.get_full_name()}.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('attendance_log')
    return render(request, 'attendance/manual_attendance.html', {'employees': employees})


@login_required
def live_status_api(request):
    all_status = get_all_today_status()
    data = [{
        'id':            s['employee'].pk,
        'name':          s['employee'].get_full_name(),
        'employee_id':   s['employee'].employee_id,
        'department':    s['employee'].department.name if s['employee'].department else '',
        'live_status':   s['live_status'],
        'first_in':      s['first_in'].strftime('%I:%M %p') if s['first_in'] else '—',
        'last_out':      s['last_out'].strftime('%I:%M %p') if s['last_out'] else '—',
        'total_hours':   s['total_hours'],
        'total_minutes': s['total_minutes'],
        'is_present':    s['is_present'],
    } for s in all_status]
    return JsonResponse({
        'employees': data,
        'timestamp': timezone.localtime(timezone.now()).strftime('%I:%M:%S %p')
    })
