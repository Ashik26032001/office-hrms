from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from employees.models import Employee, Department
from attendance.models import AttendanceEvent
from attendance.services import get_all_today_status, calculate_working_hours
from .models import CompanySettings
import json
from datetime import timedelta, date


def hr_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        if not request.user.is_admin_or_hr():
            return redirect('/employee/dashboard/')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@hr_required
def admin_dashboard(request):
    today = timezone.localdate()
    now   = timezone.now()

    total_employees = Employee.objects.filter(status='active').count()
    all_status      = get_all_today_status()

    currently_in  = sum(1 for s in all_status if s['live_status'] == 'IN')
    currently_out = total_employees - currently_in
    present_today = sum(1 for s in all_status if s['is_present'])
    absent_today  = total_employees - present_today

    late_arrivals      = 0
    total_work_minutes = 0
    for s in all_status:
        if s['first_in'] and s['employee'].shift:
            shift       = s['employee'].shift
            from datetime import datetime as dt_cls
            shift_start = timezone.make_aware(
                dt_cls.combine(today, shift.start_time)
            )
            grace = shift_start + timedelta(minutes=shift.grace_period_minutes)
            if s['first_in'] > grace:
                late_arrivals += 1
        wh = calculate_working_hours(s['employee'], today)
        total_work_minutes += wh['total_minutes']

    avg_hours = round(total_work_minutes / 60 / max(present_today, 1), 1)

    # Daily trend — last 7 days
    daily_labels  = []
    daily_present = []
    daily_absent  = []
    for i in range(6, -1, -1):
        d       = today - timedelta(days=i)
        present = AttendanceEvent.objects.filter(
            timestamp__date=d
        ).values('employee').distinct().count()
        total   = Employee.objects.filter(status='active').count()
        daily_labels.append(d.strftime('%d %b'))
        daily_present.append(present)
        daily_absent.append(max(total - present, 0))

    # Department data
    departments = Department.objects.prefetch_related('employees').all()
    dept_labels  = []
    dept_present = []
    dept_total   = []
    dept_avg_hrs = []
    for dept in departments:
        ids = dept.employees.filter(status='active').values_list('id', flat=True)
        p   = AttendanceEvent.objects.filter(
            employee_id__in=ids, timestamp__date=today
        ).values('employee').distinct().count()
        t   = dept.employees.filter(status='active').count()
        if t > 0:
            dept_labels.append(dept.name)
            dept_present.append(p)
            dept_total.append(t)
            total_mins = 0
            count      = 0
            for eid in ids:
                try:
                    emp = Employee.objects.get(pk=eid)
                    wh  = calculate_working_hours(emp, today)
                    if wh['total_minutes'] > 0:
                        total_mins += wh['total_minutes']
                        count      += 1
                except Exception:
                    pass
            dept_avg_hrs.append(round(total_mins / 60 / max(count, 1), 1) if count else 0)

    # Monthly summary
    month_labels  = []
    month_present = []
    for d in range(1, today.day + 1):
        day = date(today.year, today.month, d)
        p   = AttendanceEvent.objects.filter(
            timestamp__date=day
        ).values('employee').distinct().count()
        month_labels.append(str(d))
        month_present.append(p)

    context = {
        'total_employees': total_employees,
        'currently_in':    currently_in,
        'currently_out':   currently_out,
        'present_today':   present_today,
        'absent_today':    absent_today,
        'late_arrivals':   late_arrivals,
        'avg_hours':       avg_hours,
        'all_status':      all_status[:20],
        'daily_labels':    json.dumps(daily_labels),
        'daily_present':   json.dumps(daily_present),
        'daily_absent':    json.dumps(daily_absent),
        'dept_labels':     json.dumps(dept_labels),
        'dept_present':    json.dumps(dept_present),
        'dept_total':      json.dumps(dept_total),
        'dept_avg_hrs':    json.dumps(dept_avg_hrs),
        'month_labels':    json.dumps(month_labels),
        'month_present':   json.dumps(month_present),
        'in_count':        currently_in,
        'out_count':       currently_out,
        'today':           today,
        'now':             timezone.localtime(now),
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS PAGE
# ─────────────────────────────────────────────────────────────────────────────

@hr_required
def settings_page(request):
    cfg = CompanySettings.get()

    if request.method == 'POST':
        # Detect JSON save (from map / AJAX) vs normal form POST
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                lat    = data.get('latitude')
                lon    = data.get('longitude')
                radius = data.get('radius')
                if lat is not None:
                    cfg.office_latitude  = float(lat)
                if lon is not None:
                    cfg.office_longitude = float(lon)
                if radius is not None:
                    cfg.geofence_radius  = int(radius)
                cfg.save()
                return JsonResponse({
                    'success': True,
                    'message': f'Office location saved: {cfg.office_latitude:.6f}, {cfg.office_longitude:.6f}',
                    'latitude':  cfg.office_latitude,
                    'longitude': cfg.office_longitude,
                    'radius':    cfg.geofence_radius,
                })
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=400)

        # Normal form POST — save all settings
        cfg.company_name      = request.POST.get('company_name', cfg.company_name)
        cfg.company_email     = request.POST.get('company_email', cfg.company_email)
        cfg.company_phone     = request.POST.get('company_phone', cfg.company_phone)
        cfg.company_address   = request.POST.get('company_address', cfg.company_address)
        cfg.geofence_enabled  = request.POST.get('geofence_enabled') == 'on'
        cfg.geofence_radius   = int(request.POST.get('geofence_radius', cfg.geofence_radius))

        lat_str = request.POST.get('office_latitude', '').strip()
        lon_str = request.POST.get('office_longitude', '').strip()
        if lat_str and lon_str:
            try:
                cfg.office_latitude  = float(lat_str)
                cfg.office_longitude = float(lon_str)
            except ValueError:
                messages.error(request, 'Invalid coordinates. Enter valid numbers.')
                return render(request, 'dashboard/settings.html', {'cfg': cfg})

        cfg.save()
        messages.success(request, 'Settings saved successfully!')
        return redirect('settings_page')

    return render(request, 'dashboard/settings.html', {'cfg': cfg})


@hr_required
def get_current_location_api(request):
    """Return current saved office location as JSON."""
    cfg = CompanySettings.get()
    return JsonResponse({
        'latitude':  cfg.office_latitude,
        'longitude': cfg.office_longitude,
        'radius':    cfg.geofence_radius,
        'enabled':   cfg.geofence_enabled,
    })
