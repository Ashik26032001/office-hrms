from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta
import json

from .models import Meeting, MeetingAttendee, MeetingNotification
from .forms import MeetingForm
from employees.models import Employee


# ─── Decorators ──────────────────────────────────────────────────────────────

def hr_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        if not request.user.is_admin_or_hr():
            messages.error(request, 'HR/Admin access only.')
            return redirect('employee_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_custom(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


def _send_notifications(meeting, notification_type, message_tpl):
    """Create in-app MeetingNotification records for all attendees."""
    for ma in meeting.attendee_set.select_related('employee'):
        msg = message_tpl.format(
            title=meeting.title,
            time=timezone.localtime(meeting.scheduled_at).strftime('%d %b %Y at %I:%M %p'),
            mins=meeting.minutes_until,
        )
        MeetingNotification.objects.create(
            employee=ma.employee,
            meeting=meeting,
            notification_type=notification_type,
            message=msg,
        )


# ─── HR: Meeting List ─────────────────────────────────────────────────────────

@hr_required
def hr_meeting_list(request):
    now    = timezone.now()
    today  = timezone.localdate()

    meetings = Meeting.objects.prefetch_related(
        'attendee_set__employee__user'
    ).select_related('created_by')

    # Filters
    status_filter = request.GET.get('status', '')
    type_filter   = request.GET.get('type', '')
    search        = request.GET.get('q', '').strip()
    date_filter   = request.GET.get('date', '')

    if status_filter:
        meetings = meetings.filter(status=status_filter)
    if type_filter:
        meetings = meetings.filter(meeting_type=type_filter)
    if search:
        meetings = meetings.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    if date_filter:
        meetings = meetings.filter(scheduled_at__date=date_filter)

    # Auto-update statuses
    for m in Meeting.objects.filter(status='scheduled'):
        if m.scheduled_at <= now <= m.ends_at:
            m.status = 'ongoing'
            m.save(update_fields=['status'])
        elif m.ends_at < now:
            m.status = 'completed'
            m.save(update_fields=['status'])

    upcoming   = meetings.filter(status='scheduled', scheduled_at__gte=now).order_by('scheduled_at')
    ongoing    = meetings.filter(status='ongoing')
    past       = meetings.filter(status__in=['completed', 'cancelled']).order_by('-scheduled_at')[:20]
    cancelled  = meetings.filter(status='cancelled').order_by('-scheduled_at')

    # KPIs
    total_today    = Meeting.objects.filter(scheduled_at__date=today).count()
    total_upcoming = Meeting.objects.filter(status='scheduled', scheduled_at__gte=now).count()
    total_this_week = Meeting.objects.filter(
        scheduled_at__date__gte=today,
        scheduled_at__date__lte=today + timedelta(days=7)
    ).count()
    total_all = Meeting.objects.count()

    context = {
        'upcoming':        upcoming,
        'ongoing':         ongoing,
        'past':            past,
        'total_today':     total_today,
        'total_upcoming':  total_upcoming,
        'total_this_week': total_this_week,
        'total_all':       total_all,
        'status_filter':   status_filter,
        'type_filter':     type_filter,
        'search':          search,
        'date_filter':     date_filter,
        'type_choices':    Meeting.TYPE_CHOICES,
        'status_choices':  Meeting.STATUS_CHOICES,
        'now':             now,
    }
    return render(request, 'meetings/hr_meeting_list.html', context)


# ─── HR: Create Meeting ───────────────────────────────────────────────────────

@hr_required
def hr_create_meeting(request):
    if request.method == 'POST':
        form = MeetingForm(request.POST)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.created_by = request.user
            meeting.save()

            # Save attendees via through model
            for emp in form.cleaned_data['attendees']:
                MeetingAttendee.objects.create(meeting=meeting, employee=emp)

            # Send invite notifications
            _send_notifications(
                meeting, 'invite',
                '📅 You have been invited to "{title}" on {time}.'
            )

            messages.success(request, f'Meeting "{meeting.title}" scheduled successfully!')
            return redirect('hr_meeting_detail', pk=meeting.pk)
    else:
        form = MeetingForm()
    return render(request, 'meetings/meeting_form.html', {
        'form': form, 'action': 'Schedule',
        'employees': Employee.objects.filter(status='active').select_related('user'),
    })


# ─── HR: Edit Meeting ─────────────────────────────────────────────────────────

@hr_required
def hr_edit_meeting(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    if request.method == 'POST':
        form = MeetingForm(request.POST, instance=meeting)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.save()
            # Update attendees
            current_ids = set(meeting.attendees.values_list('id', flat=True))
            new_ids     = set(emp.pk for emp in form.cleaned_data['attendees'])

            # Add new
            for emp in form.cleaned_data['attendees']:
                if emp.pk not in current_ids:
                    MeetingAttendee.objects.get_or_create(meeting=meeting, employee=emp)
                    MeetingNotification.objects.create(
                        employee=emp, meeting=meeting,
                        notification_type='invite',
                        message=f'📅 You have been invited to "{meeting.title}" on '
                                f'{timezone.localtime(meeting.scheduled_at).strftime("%d %b %Y at %I:%M %p")}.',
                    )
            # Remove dropped
            for eid in current_ids - new_ids:
                MeetingAttendee.objects.filter(meeting=meeting, employee_id=eid).delete()

            # Notify existing attendees of update
            _send_notifications(
                meeting, 'update',
                '✏️ Meeting "{title}" has been updated. New time: {time}.'
            )

            messages.success(request, f'Meeting "{meeting.title}" updated!')
            return redirect('hr_meeting_detail', pk=meeting.pk)
    else:
        form = MeetingForm(instance=meeting,
                           initial={'attendees': meeting.attendees.all()})
    return render(request, 'meetings/meeting_form.html', {
        'form': form, 'action': 'Edit', 'meeting': meeting,
        'employees': Employee.objects.filter(status='active').select_related('user'),
    })


# ─── HR: Meeting Detail ───────────────────────────────────────────────────────

@hr_required
def hr_meeting_detail(request, pk):
    meeting = get_object_or_404(
        Meeting.objects.prefetch_related('attendee_set__employee__user'),
        pk=pk
    )
    attendees = meeting.attendee_set.select_related('employee__user').all()
    context = {
        'meeting':   meeting,
        'attendees': attendees,
        'now':       timezone.now(),
    }
    return render(request, 'meetings/meeting_detail.html', context)


# ─── HR: Cancel Meeting ───────────────────────────────────────────────────────

@hr_required
def hr_cancel_meeting(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    if request.method == 'POST':
        meeting.status = 'cancelled'
        meeting.save(update_fields=['status'])
        _send_notifications(
            meeting, 'cancel',
            '❌ Meeting "{title}" scheduled for {time} has been cancelled.'
        )
        messages.warning(request, f'Meeting "{meeting.title}" cancelled.')
        return redirect('hr_meeting_list')
    return render(request, 'meetings/meeting_confirm_cancel.html', {'meeting': meeting})


# ─── HR: Delete Meeting ───────────────────────────────────────────────────────

@hr_required
def hr_delete_meeting(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    if request.method == 'POST':
        name = meeting.title
        meeting.delete()
        messages.success(request, f'Meeting "{name}" deleted.')
        return redirect('hr_meeting_list')
    return render(request, 'meetings/meeting_confirm_delete.html', {'meeting': meeting})


# ─── Employee: My Meetings ────────────────────────────────────────────────────

@login_required_custom
def employee_meetings(request):
    try:
        employee = request.user.employee_profile
    except Exception:
        messages.error(request, 'No employee profile found.')
        return redirect('employee_dashboard')

    now = timezone.now()

    # Do NOT auto-mark all as read here — let the user dismiss them via the bell

    attendances = MeetingAttendee.objects.filter(
        employee=employee
    ).select_related('meeting__created_by').order_by('meeting__scheduled_at')

    upcoming = attendances.filter(
        meeting__status='scheduled',
        meeting__scheduled_at__gte=now
    )
    ongoing  = attendances.filter(meeting__status='ongoing')
    past     = attendances.filter(
        meeting__status__in=['completed', 'cancelled']
    ).order_by('-meeting__scheduled_at')[:20]

    # Next meeting countdown
    next_ma = upcoming.first()

    context = {
        'employee':  employee,
        'upcoming':  upcoming,
        'ongoing':   ongoing,
        'past':      past,
        'next_ma':   next_ma,
        'now':       now,
    }
    return render(request, 'meetings/employee_meetings.html', context)


# ─── Employee: RSVP ──────────────────────────────────────────────────────────

@login_required_custom
def rsvp(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        employee = request.user.employee_profile
    except Exception:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    ma = get_object_or_404(MeetingAttendee, meeting_id=pk, employee=employee)
    data = json.loads(request.body)
    status_val = data.get('rsvp')
    if status_val not in ['accepted', 'declined']:
        return JsonResponse({'error': 'Invalid RSVP value'}, status=400)

    ma.rsvp = status_val
    ma.save(update_fields=['rsvp'])
    return JsonResponse({'success': True, 'rsvp': ma.rsvp})


# ─── AJAX: Poll for 5-min reminder notifications ─────────────────────────────

@login_required_custom
def poll_notifications(request):
    """
    Called every 15 s from the browser.
    Returns:
      - notifications: unread MeetingNotification rows
      - alert_meetings: meetings starting within 10 min (for the full-page banner)
    """
    try:
        employee = request.user.employee_profile
    except Exception:
        return JsonResponse({'notifications': [], 'count': 0, 'alert_meetings': []})

    # Synchronous reminder check
    from .notification_engine import fire_pending_reminders
    try:
        fire_pending_reminders()
    except Exception:
        pass

    now = timezone.now()

    # ── Unread bell notifications ──────────────────────────────────────────
    unread = MeetingNotification.objects.filter(
        employee=employee, is_read=False
    ).select_related('meeting').order_by('-created_at')[:30]

    notif_data = []
    for n in unread:
        notif_data.append({
            'id':         n.pk,
            'type':       n.notification_type,
            'message':    n.message,
            'meeting_id': n.meeting_id,
            'link':       n.meeting.meeting_link or '',
            'time':       n.created_at.isoformat(),
        })

    # ── Alert meetings: ONLY those whose time has just arrived (minutes_until == 0) ──
    # Window: scheduled_at between (now - 1 min) and (now + 1 min) → countdown just hit zero
    alert_mas = MeetingAttendee.objects.filter(
        employee=employee,
        meeting__status__in=['scheduled', 'ongoing'],
        meeting__scheduled_at__gte=now - timedelta(minutes=1),
        meeting__scheduled_at__lte=now + timedelta(minutes=1),
    ).select_related('meeting')

    alert_meetings_data = []
    for ma in alert_mas:
        m = ma.meeting
        mins_until = int((m.scheduled_at - now).total_seconds() / 60)
        # alert_key = the exact minute bucket so the same meeting fires once per minute slot
        alert_key = timezone.localtime(m.scheduled_at).strftime('%Y%m%d%H%M')
        alert_meetings_data.append({
            'id':           m.pk,
            'title':        m.title,
            'link':         m.meeting_link or '',
            'formatted_time': timezone.localtime(m.scheduled_at).strftime('%I:%M %p'),
            'type_display': m.get_meeting_type_display(),
            'minutes_until': mins_until,
            'alert_key':    alert_key,
        })

    return JsonResponse({
        'notifications':  notif_data,
        'count':          len(notif_data),
        'alert_meetings': alert_meetings_data,
    })


# ─── AJAX: Mark notification read ────────────────────────────────────────────

@login_required_custom
def mark_notification_read(request, nid):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        employee = request.user.employee_profile
    except Exception:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    MeetingNotification.objects.filter(pk=nid, employee=employee).update(is_read=True)
    return JsonResponse({'success': True})


# ─── AJAX: Upcoming meetings JSON for browser timers ─────────────────────────

@login_required_custom
def upcoming_meetings_json(request):
    """
    Returns all upcoming scheduled meetings for the logged-in employee
    as a JSON array with ISO timestamps — used by the browser to start
    per-meeting countdown timers that fire showMeetingAlert() at t=0.
    """
    try:
        employee = request.user.employee_profile
    except Exception:
        return JsonResponse({'meetings': []})

    now = timezone.now()

    mas = MeetingAttendee.objects.filter(
        employee=employee,
        meeting__status='scheduled',
        meeting__scheduled_at__gt=now,
    ).select_related('meeting').order_by('meeting__scheduled_at')

    data = []
    for ma in mas:
        m = ma.meeting
        data.append({
            'id':           m.pk,
            'title':        m.title,
            'iso':          m.scheduled_at.isoformat(),   # e.g. 2026-11-14T17:32:00+00:00
            'link':         m.meeting_link or '',
            'type_display': m.get_meeting_type_display(),
            'formatted_time': timezone.localtime(m.scheduled_at).strftime('%I:%M %p'),
            'minutes_until': int((m.scheduled_at - now).total_seconds() / 60),
            'alert_key':    'timer',
        })

    return JsonResponse({'meetings': data})

@login_required_custom
def unread_count(request):
    try:
        employee = request.user.employee_profile
        count = MeetingNotification.objects.filter(employee=employee, is_read=False).count()
    except Exception:
        count = 0
    return JsonResponse({'count': count})
