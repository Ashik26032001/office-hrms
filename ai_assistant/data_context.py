"""
data_context.py
===============
Builds a rich structured context dict from the Django DB for a given user.
This context is both:
  1. Used directly by the rule-based engine (fast, always available).
  2. Serialised into a system prompt for Ollama (when available).
"""

from django.utils import timezone
from datetime import timedelta, date as date_cls
import json


def get_context_for_user(user):
    """Return a dict with all HRMS data relevant to `user`."""
    from employees.models import Employee, Department
    from attendance.models import AttendanceEvent
    from work_progress.models import Project, Task
    from meetings.models import Meeting, MeetingAttendee, MeetingNotification

    now   = timezone.now()
    today = timezone.localdate()
    ctx   = {'role': user.role, 'name': user.get_full_name() or user.username, 'today': str(today)}

    # ── Employee-specific context ───────────────────────────────────────────
    if user.role == 'employee':
        try:
            emp = user.employee_profile
        except Exception:
            return ctx

        ctx['employee_id']  = emp.employee_id
        ctx['designation']  = emp.designation
        ctx['department']   = str(emp.department) if emp.department else '—'
        ctx['joining_date'] = str(emp.joining_date)

        # Attendance this month
        month_start = today.replace(day=1)
        events_this_month = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date__gte=month_start,
        )
        days_present = events_this_month.filter(
            event_type='IN'
        ).values('timestamp__date').distinct().count()

        # Working days in month so far
        working_days = sum(
            1 for d in range(1, today.day + 1)
            if date_cls(today.year, today.month, d).weekday() < 5
        )
        days_absent = max(0, working_days - days_present)
        ctx['attendance'] = {
            'days_present_this_month': days_present,
            'days_absent_this_month':  days_absent,
            'working_days_so_far':     working_days,
            'attendance_percent':      round(days_present / max(working_days, 1) * 100),
        }

        # Today's status
        today_events = AttendanceEvent.objects.filter(
            employee=emp, timestamp__date=today
        ).order_by('timestamp')
        ctx['today_status'] = 'IN' if today_events.filter(event_type='IN').exists() else 'NOT CHECKED IN'
        ctx['today_checkin'] = str(
            timezone.localtime(today_events.filter(event_type='IN').first().timestamp).strftime('%I:%M %p')
        ) if today_events.filter(event_type='IN').exists() else None

        # Last 7 days attendance
        week_days = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            checked_in = AttendanceEvent.objects.filter(
                employee=emp, timestamp__date=d, event_type='IN'
            ).exists()
            week_days.append({'date': str(d), 'present': checked_in})
        ctx['last_7_days'] = week_days

        # Tasks
        my_tasks = Task.objects.filter(assigned_to=emp).select_related('project')
        ctx['tasks'] = {
            'total':        my_tasks.count(),
            'todo':         my_tasks.filter(status='todo').count(),
            'open':         my_tasks.filter(status='open').count(),
            'under_review': my_tasks.filter(status='under_review').count(),
            'done':         my_tasks.filter(status='done').count(),
            'overdue':      my_tasks.filter(end_date__lt=today).exclude(status='done').count(),
            'pending':      my_tasks.exclude(status='done').count(),
        }
        # Nearest deadline
        next_task = my_tasks.exclude(status='done').filter(
            end_date__gte=today
        ).order_by('end_date').first()
        ctx['next_task_deadline'] = {
            'title':    next_task.title,
            'deadline': str(next_task.end_date),
            'status':   next_task.status,
            'project':  next_task.project.name,
        } if next_task else None

        # Projects
        my_projects = emp.projects.filter(is_active=True)
        ctx['projects'] = [
            {
                'name':     p.name,
                'tasks':    p.tasks.count(),
                'done':     p.tasks.filter(status='done').count(),
                'accuracy': p.on_time_accuracy(),
            }
            for p in my_projects
        ]

        # Meetings
        my_mas = MeetingAttendee.objects.filter(employee=emp).select_related('meeting')
        upcoming_meetings = my_mas.filter(
            meeting__status='scheduled', meeting__scheduled_at__gte=now
        ).order_by('meeting__scheduled_at')
        ctx['meetings'] = {
            'upcoming_count': upcoming_meetings.count(),
            'next': {
                'title':  upcoming_meetings.first().meeting.title,
                'time':   timezone.localtime(upcoming_meetings.first().meeting.scheduled_at).strftime('%d %b %Y at %I:%M %p'),
                'link':   upcoming_meetings.first().meeting.meeting_link or 'No link',
            } if upcoming_meetings.exists() else None,
        }

        # Unread notifications
        from meetings.models import MeetingNotification
        ctx['unread_notifications'] = MeetingNotification.objects.filter(
            employee=emp, is_read=False
        ).count()

    # ── HR / Admin context ──────────────────────────────────────────────────
    else:
        total_employees = Employee.objects.filter(status='active').count()
        ctx['total_employees'] = total_employees

        # Today attendance
        present_today = AttendanceEvent.objects.filter(
            timestamp__date=today, event_type='IN'
        ).values('employee').distinct().count()
        ctx['today_attendance'] = {
            'present': present_today,
            'absent':  max(0, total_employees - present_today),
            'rate':    round(present_today / max(total_employees, 1) * 100),
        }

        # Late arrivals today
        from employees.models import Shift
        late = 0
        for emp in Employee.objects.filter(status='active').select_related('shift'):
            if emp.shift:
                first_in = AttendanceEvent.objects.filter(
                    employee=emp, timestamp__date=today, event_type='IN'
                ).order_by('timestamp').first()
                if first_in:
                    shift_start = timezone.make_aware(
                        timezone.datetime.combine(today, emp.shift.start_time)
                    )
                    grace = shift_start + timedelta(minutes=emp.shift.grace_period_minutes)
                    if first_in.timestamp > grace:
                        late += 1
        ctx['late_arrivals_today'] = late

        # Department-wise
        departments = Department.objects.prefetch_related('employees').all()
        dept_data = []
        for dept in departments:
            ids = dept.employees.filter(status='active').values_list('id', flat=True)
            p   = AttendanceEvent.objects.filter(
                employee_id__in=ids, timestamp__date=today, event_type='IN'
            ).values('employee').distinct().count()
            dept_data.append({'dept': dept.name, 'total': len(ids), 'present': p})
        ctx['departments'] = dept_data

        # This month attendance
        month_start = today.replace(day=1)
        ctx['this_month'] = {
            'attendance_events': AttendanceEvent.objects.filter(
                timestamp__date__gte=month_start
            ).count(),
        }

        # Tasks / projects
        all_tasks = Task.objects.all()
        ctx['all_tasks'] = {
            'total':        all_tasks.count(),
            'todo':         all_tasks.filter(status='todo').count(),
            'open':         all_tasks.filter(status='open').count(),
            'under_review': all_tasks.filter(status='under_review').count(),
            'done':         all_tasks.filter(status='done').count(),
            'overdue':      all_tasks.filter(end_date__lt=today).exclude(status='done').count(),
        }
        all_projects = Project.objects.all()
        ctx['all_projects'] = {
            'total':   all_projects.count(),
            'active':  all_projects.filter(is_active=True).count(),
        }

        # Delayed projects
        delayed = [
            p.name for p in all_projects
            if p.end_date and p.end_date < today and p.tasks.exclude(status='done').exists()
        ]
        ctx['delayed_projects'] = delayed

        # Employees with pending tasks
        emp_pending = []
        for emp in Employee.objects.filter(status='active').select_related('user')[:20]:
            pending = Task.objects.filter(assigned_to=emp).exclude(status='done').count()
            if pending:
                emp_pending.append({'name': emp.get_full_name(), 'pending': pending})
        ctx['employees_with_pending_tasks'] = emp_pending

        # Frequent late arrivals (this month)
        late_emp = []
        for emp in Employee.objects.filter(status='active').select_related('user', 'shift'):
            if not emp.shift:
                continue
            count = 0
            for d in range(1, today.day + 1):
                day = date_cls(today.year, today.month, d)
                if day.weekday() >= 5:
                    continue
                first_in = AttendanceEvent.objects.filter(
                    employee=emp, timestamp__date=day, event_type='IN'
                ).order_by('timestamp').first()
                if first_in:
                    shift_start = timezone.make_aware(
                        timezone.datetime.combine(day, emp.shift.start_time)
                    )
                    grace = shift_start + timedelta(minutes=emp.shift.grace_period_minutes)
                    if first_in.timestamp > grace:
                        count += 1
            if count >= 3:
                late_emp.append({'name': emp.get_full_name(), 'late_days': count})
        ctx['frequent_late_employees'] = late_emp

        # Upcoming meetings
        upcoming_m = Meeting.objects.filter(
            status='scheduled', scheduled_at__gte=now
        ).order_by('scheduled_at')[:5]
        ctx['upcoming_meetings'] = [
            {
                'title': m.title,
                'time':  timezone.localtime(m.scheduled_at).strftime('%d %b %Y at %I:%M %p'),
                'attendees': m.attendee_set.count(),
            }
            for m in upcoming_m
        ]

    return ctx


def context_to_system_prompt(ctx):
    """Convert the context dict into a concise system prompt for Ollama."""
    role = ctx.get('role', 'employee')
    name = ctx.get('name', 'User')
    today = ctx.get('today', '')

    lines = [
        f"You are SmartHR AI Assistant, an intelligent HR management assistant.",
        f"Today is {today}. You are speaking to {name} who is a {role.upper()} in this organization.",
        f"Your job: answer questions accurately using ONLY the data provided below.",
        f"Be concise, friendly, and professional. Use bullet points where helpful.",
        f"NEVER invent data. If data is not in the context, say so clearly.",
        f"",
        f"=== LIVE DATABASE CONTEXT ===",
        json.dumps(ctx, indent=2, default=str),
        f"=== END CONTEXT ===",
        f"",
        f"Answer the user's question based strictly on the data above.",
    ]
    return '\n'.join(lines)
