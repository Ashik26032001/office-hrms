from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from attendance.models import AttendanceEvent
from attendance.services import calculate_working_hours
from employees.models import Employee, Department
from datetime import date, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def hr_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        if not request.user.is_admin_or_hr():
            return redirect('/employee/dashboard/')
        return view_func(request, *args, **kwargs)
    return wrapper


@hr_required
def reports_home(request):
    today = timezone.localdate()
    return render(request, 'reports/reports_home.html', {'today': today})


@hr_required
def daily_report(request):
    date_str = request.GET.get('date', timezone.localdate().isoformat())
    dept_filter = request.GET.get('dept', '')
    try:
        report_date = date.fromisoformat(date_str)
    except ValueError:
        report_date = timezone.localdate()

    employees = Employee.objects.filter(status='active').select_related('user', 'department', 'shift')
    if dept_filter:
        employees = employees.filter(department_id=dept_filter)

    report_data = []
    for emp in employees:
        wh = calculate_working_hours(emp, report_date)
        first_in = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=report_date, event_type='IN'
        ).order_by('timestamp').first()
        last_out = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=report_date, event_type='OUT'
        ).order_by('-timestamp').first()

        is_present = AttendanceEvent.objects.filter(employee=emp, timestamp__date=report_date).exists()

        # Check late arrival
        is_late = False
        if first_in and emp.shift:
            shift_start = timezone.make_aware(
                timezone.datetime.combine(report_date, emp.shift.start_time)
            )
            grace = shift_start + timedelta(minutes=emp.shift.grace_period_minutes)
            is_late = timezone.localtime(first_in.timestamp) > grace

        report_data.append({
            'emp': emp,
            'is_present': is_present,
            'is_late': is_late,
            'first_in': timezone.localtime(first_in.timestamp) if first_in else None,
            'last_out': timezone.localtime(last_out.timestamp) if last_out else None,
            'hours': wh['hours'],
            'minutes': wh['minutes'],
        })

    present_count = sum(1 for r in report_data if r['is_present'])
    absent_count = len(report_data) - present_count

    departments = Department.objects.all()
    context = {
        'report_data': report_data,
        'report_date': report_date,
        'present_count': present_count,
        'absent_count': absent_count,
        'departments': departments,
        'dept_filter': dept_filter,
    }
    return render(request, 'reports/daily_report.html', context)


@hr_required
def export_daily_excel(request):
    date_str = request.GET.get('date', timezone.localdate().isoformat())
    try:
        report_date = date.fromisoformat(date_str)
    except ValueError:
        report_date = timezone.localdate()

    employees = Employee.objects.filter(status='active').select_related('user', 'department')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Attendance {report_date}"

    # Styles
    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    header_align = Alignment(horizontal='center', vertical='center')
    thin = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Title row
    ws.merge_cells('A1:J1')
    ws['A1'] = f"Daily Attendance Report - {report_date.strftime('%d %B %Y')}"
    ws['A1'].font = Font(bold=True, size=14, color="1E3A5F")
    ws['A1'].alignment = Alignment(horizontal='center')

    headers = ['#', 'Employee ID', 'Name', 'Department', 'Designation',
               'Status', 'Check In', 'Check Out', 'Working Hours', 'Late']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin
        ws.column_dimensions[cell.column_letter].width = 16

    present_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    absent_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")

    for idx, emp in enumerate(employees, 1):
        wh = calculate_working_hours(emp, report_date)
        first_in = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=report_date, event_type='IN'
        ).order_by('timestamp').first()
        last_out = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=report_date, event_type='OUT'
        ).order_by('-timestamp').first()

        is_present = AttendanceEvent.objects.filter(employee=emp, timestamp__date=report_date).exists()
        row_fill = present_fill if is_present else absent_fill

        row = idx + 3
        values = [
            idx,
            emp.employee_id,
            emp.get_full_name(),
            emp.department.name if emp.department else '',
            emp.designation,
            'Present' if is_present else 'Absent',
            timezone.localtime(first_in.timestamp).strftime('%I:%M %p') if first_in else '—',
            timezone.localtime(last_out.timestamp).strftime('%I:%M %p') if last_out else '—',
            f"{wh['hours']}h {wh['minutes']}m" if is_present else '—',
            'Yes' if (first_in and emp.shift and
                      timezone.localtime(first_in.timestamp).time() >
                      __import__('datetime').time(emp.shift.start_time.hour,
                                                  emp.shift.start_time.minute)) else 'No',
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.fill = row_fill
            cell.border = thin
            cell.alignment = Alignment(horizontal='center')

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="attendance_{report_date}.xlsx"'
    wb.save(response)
    return response


@hr_required
def monthly_report(request):
    today = timezone.localdate()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    dept_filter = request.GET.get('dept', '')

    employees = Employee.objects.filter(status='active').select_related('user', 'department')
    if dept_filter:
        employees = employees.filter(department_id=dept_filter)

    # Working days in the month
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    working_days = []
    for d in range(1, last_day + 1):
        day = date(year, month, d)
        if day.weekday() < 5 and day <= today:  # Mon-Fri and not future
            working_days.append(day)

    report_data = []
    for emp in employees:
        present_days = 0
        total_minutes = 0
        for d in working_days:
            is_p = AttendanceEvent.objects.filter(employee=emp, timestamp__date=d).exists()
            if is_p:
                present_days += 1
                wh = calculate_working_hours(emp, d)
                total_minutes += wh['total_minutes']

        absent_days = len(working_days) - present_days
        avg_hrs = round(total_minutes / 60 / max(present_days, 1), 1) if present_days else 0

        report_data.append({
            'emp': emp,
            'present_days': present_days,
            'absent_days': absent_days,
            'total_hours': total_minutes // 60,
            'total_minutes': total_minutes % 60,
            'avg_hours': avg_hrs,
            'attendance_pct': round(present_days / max(len(working_days), 1) * 100, 1),
        })

    departments = Department.objects.all()
    import calendar
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years = list(range(2024, today.year + 2))

    context = {
        'report_data': report_data,
        'month': month,
        'year': year,
        'month_name': calendar.month_name[month],
        'departments': departments,
        'dept_filter': dept_filter,
        'months': months,
        'years': years,
        'working_days_count': len(working_days),
    }
    return render(request, 'reports/monthly_report.html', context)
