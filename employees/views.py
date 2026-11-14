from django.shortcuts import render, redirect, get_object_or_404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from accounts.models import CustomUser
from .models import Employee, Department, Shift
from .forms import EmployeeCreateForm, EmployeeEditForm, DepartmentForm, ShiftForm
from attendance.models import AttendanceEvent
from django.utils import timezone
from django.db.models import Q
import qrcode
import io


def hr_required(view_func):
    """Decorator: only admin/HR can access."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        if not request.user.is_admin_or_hr():
            messages.error(request, "Access denied. HR/Admin only.")
            return redirect('/employee/dashboard/')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── DYNAMIC QR CODE VIEW ─────────────────────────────────────────────────────
@login_required
def employee_qr_image(request, pk):
    """
    Generates QR code image on the fly from the employee's qr_token.
    This works on any server including Railway where media files don't persist.
    Only the employee themselves or HR/Admin can access their QR.
    """
    emp = get_object_or_404(Employee, pk=pk)

    # Security: employee can only see their own QR; HR/Admin can see all
    if not request.user.is_admin_or_hr():
        try:
            if request.user.employee_profile.pk != emp.pk:
                return HttpResponse('Forbidden', status=403)
        except Exception:
            return HttpResponse('Forbidden', status=403)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(str(emp.qr_token))
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e3a5f", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return HttpResponse(buffer.read(), content_type='image/png')


@hr_required
def employee_list(request):
    query = request.GET.get('q', '')
    dept_filter = request.GET.get('dept', '')
    status_filter = request.GET.get('status', '')

    employees = Employee.objects.select_related('user', 'department', 'shift').all()

    if query:
        employees = employees.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(designation__icontains=query)
        )
    if dept_filter:
        employees = employees.filter(department_id=dept_filter)
    if status_filter:
        employees = employees.filter(status=status_filter)

    # Annotate live status
    today = timezone.localdate()
    for emp in employees:
        last_event = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=today
        ).order_by('-timestamp').first()
        emp.live_status = last_event.event_type if last_event else 'OUT'
        emp.last_event = last_event

    departments = Department.objects.all()
    context = {
        'employees': employees,
        'departments': departments,
        'query': query,
        'dept_filter': dept_filter,
        'status_filter': status_filter,
        'total': employees.count(),
    }
    return render(request, 'employees/employee_list.html', context)


@hr_required
def employee_create(request):
    form = EmployeeCreateForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        user = CustomUser.objects.create_user(
            username=d['username'],
            password=d['password'],
            first_name=d['first_name'],
            last_name=d['last_name'],
            email=d['email'],
            phone=d['phone'],
            role=CustomUser.ROLE_EMPLOYEE,
        )
        emp = Employee(
            user=user,
            employee_id=d['employee_id'],
            department=d['department'],
            shift=d['shift'],
            designation=d['designation'],
            joining_date=d['joining_date'],
        )
        if d.get('photo'):
            emp.photo = d['photo']
        emp.save()
        messages.success(request, f"Employee {user.get_full_name()} created successfully!")
        return redirect('employee_list')

    return render(request, 'employees/employee_form.html', {'form': form, 'action': 'Add'})


@hr_required
def employee_edit(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    initial = {
        'first_name': emp.user.first_name,
        'last_name': emp.user.last_name,
        'email': emp.user.email,
        'phone': emp.user.phone,
    }
    form = EmployeeEditForm(request.POST or None, request.FILES or None, instance=emp, initial=initial)
    if request.method == 'POST' and form.is_valid():
        emp_obj = form.save(commit=False)
        emp_obj.user.first_name = form.cleaned_data['first_name']
        emp_obj.user.last_name = form.cleaned_data['last_name']
        emp_obj.user.email = form.cleaned_data['email']
        emp_obj.user.phone = form.cleaned_data.get('phone', '')
        emp_obj.user.save()
        emp_obj.save()
        messages.success(request, "Employee updated successfully.")
        return redirect('employee_list')

    return render(request, 'employees/employee_form.html', {'form': form, 'action': 'Edit', 'emp': emp})


@hr_required
def employee_detail(request, pk):
    emp = get_object_or_404(Employee.objects.select_related('user', 'department', 'shift'), pk=pk)
    today = timezone.localdate()
    recent_events = AttendanceEvent.objects.filter(employee=emp).order_by('-timestamp')[:20]
    last_event_today = AttendanceEvent.objects.filter(
        employee=emp, timestamp__date=today
    ).order_by('-timestamp').first()
    live_status = last_event_today.event_type if last_event_today else 'OUT'

    context = {
        'emp': emp,
        'recent_events': recent_events,
        'live_status': live_status,
    }
    return render(request, 'employees/employee_detail.html', context)


@hr_required
def employee_delete(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        name = emp.get_full_name()
        emp.user.delete()  # Cascades to employee
        messages.success(request, f"Employee {name} deleted.")
        return redirect('employee_list')
    return render(request, 'employees/employee_confirm_delete.html', {'emp': emp})


@hr_required
def regenerate_qr(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    emp.generate_qr()
    emp.save(update_fields=['qr_image'])
    messages.success(request, "QR code regenerated.")
    return redirect('employee_detail', pk=pk)


# ─── FINGERPRINT MANAGEMENT ───────────────────────────────────────────────────

@hr_required
def finger_management(request, pk):
    """Admin page to view/manage employee's finger credentials."""
    from employees.models import FingerCredential
    emp = get_object_or_404(Employee.objects.select_related('user', 'department'), pk=pk)
    credentials  = FingerCredential.objects.filter(employee=emp, is_active=True)
    slots_used   = credentials.count()
    empty_count  = max(0, emp.max_fingers_allowed - slots_used)
    empty_slots  = range(empty_count)
    return render(request, 'employees/finger_management.html', {
        'emp':         emp,
        'credentials': credentials,
        'empty_slots': empty_slots,
    })


@hr_required
def set_max_fingers(request, pk):
    """Admin sets how many fingers an employee can enroll."""
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        max_f = int(request.POST.get('max_fingers', 3))
        emp.max_fingers_allowed = max(1, min(5, max_f))
        emp.save(update_fields=['max_fingers_allowed'])
        messages.success(request, f"Max fingers set to {emp.max_fingers_allowed}.")
    return redirect('finger_management', pk=pk)


@hr_required
def delete_finger(request, cred_pk):
    """Admin deletes one finger credential."""
    from employees.models import FingerCredential
    cred = get_object_or_404(FingerCredential, pk=cred_pk)
    emp_pk = cred.employee.pk
    if request.method == 'POST':
        cred.is_active = False
        cred.save(update_fields=['is_active'])
        # Update legacy flag if no active credentials left
        if not FingerCredential.objects.filter(employee=cred.employee, is_active=True).exists():
            cred.employee.webauthn_enrolled = False
            cred.employee.save(update_fields=['webauthn_enrolled'])
        messages.success(request, "Finger credential removed.")
    return redirect('finger_management', pk=emp_pk)


@hr_required
def delete_all_fingers(request, pk):
    """Admin removes ALL finger credentials for an employee."""
    from employees.models import FingerCredential
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        FingerCredential.objects.filter(employee=emp).update(is_active=False)
        emp.webauthn_enrolled      = False
        emp.webauthn_credential_id = None
        emp.webauthn_public_key    = None
        emp.save(update_fields=['webauthn_enrolled', 'webauthn_credential_id', 'webauthn_public_key'])
        messages.success(request, "All fingerprints removed.")
    return redirect('finger_management', pk=pk)


# --- Department ---

@hr_required
def department_list(request):
    departments = Department.objects.prefetch_related('employees').all()
    return render(request, 'employees/department_list.html', {'departments': departments})


@hr_required
def department_create(request):
    form = DepartmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Department created.")
        return redirect('department_list')
    return render(request, 'employees/department_form.html', {'form': form, 'action': 'Add'})


@hr_required
def department_edit(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=dept)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Department updated.")
        return redirect('department_list')
    return render(request, 'employees/department_form.html', {'form': form, 'action': 'Edit'})


# --- Employee self dashboard ---

@login_required
def employee_self_dashboard(request):
    if request.user.is_admin_or_hr():
        return redirect('/dashboard/')

    try:
        emp = request.user.employee_profile
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found. Contact HR.")
        return redirect('/accounts/login/')

    today = timezone.localdate()
    today_events = AttendanceEvent.objects.filter(
        employee=emp, timestamp__date=today
    ).order_by('timestamp')

    last_event = today_events.last()
    live_status = last_event.event_type if last_event else 'OUT'

    # Calculate today's working hours
    total_minutes = 0
    events = list(today_events)
    i = 0
    sessions = []
    while i < len(events):
        if events[i].event_type == 'IN':
            in_time = events[i].timestamp
            out_time = None
            if i + 1 < len(events) and events[i + 1].event_type == 'OUT':
                out_time = events[i + 1].timestamp
                diff = (out_time - in_time).seconds // 60
                total_minutes += diff
                sessions.append({'in': in_time, 'out': out_time, 'minutes': diff})
                i += 2
                continue
            else:
                sessions.append({'in': in_time, 'out': None, 'minutes': None})
        i += 1

    hours = total_minutes // 60
    minutes = total_minutes % 60

    # Recent attendance (last 10 days)
    from django.db.models.functions import TruncDate
    recent_events = AttendanceEvent.objects.filter(
        employee=emp
    ).order_by('-timestamp')[:30]

    context = {
        'emp': emp,
        'live_status': live_status,
        'today_events': today_events,
        'sessions': sessions,
        'total_hours': hours,
        'total_minutes_rem': minutes,
        'recent_events': recent_events,
        'today': today,
    }
    return render(request, 'employees/employee_dashboard.html', context)
