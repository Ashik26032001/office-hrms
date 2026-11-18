"""
Notification Engine — no Celery, no Redis required.

Strategy:
  - Every Django request runs a lightweight "tick" via middleware.
  - The tick fires DB-based reminders for meetings starting within the next 6 minutes
    whose attendees haven't been notified yet.
  - A module-level threading.Timer is used to run the check every 60 s in the
    background (started once when Django loads, safe with DEBUG + production).
  - The browser polls /meetings/notifications/poll/ every 30 s and reads the
    already-written DB rows — so the bell icon always reflects live state.
"""

import threading
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

_timer_started = False
_lock = threading.Lock()


def fire_pending_reminders():
    """Write MeetingNotification rows for meetings whose time has arrived (within ±1 min)."""
    try:
        from django.utils import timezone
        from .models import Meeting, MeetingAttendee, MeetingNotification

        now = timezone.now()

        # Only meetings starting right now (within ±1 minute window)
        upcoming = Meeting.objects.filter(
            status='scheduled',
            scheduled_at__gte=now - timedelta(minutes=1),
            scheduled_at__lte=now + timedelta(minutes=1),
            reminder_sent=False,
        ).prefetch_related('attendee_set__employee')

        for meeting in upcoming:
            local_time = timezone.localtime(meeting.scheduled_at).strftime('%I:%M %p')

            for ma in meeting.attendee_set.select_related('employee'):
                already = MeetingNotification.objects.filter(
                    employee=ma.employee,
                    meeting=meeting,
                    notification_type='reminder',
                ).exists()
                if not already:
                    MeetingNotification.objects.create(
                        employee=ma.employee,
                        meeting=meeting,
                        notification_type='reminder',
                        message=f'⏰ "{meeting.title}" is starting NOW! ({local_time})',
                        is_read=False,
                    )
                    ma.notified = True
                    ma.save(update_fields=['notified'])

            meeting.reminder_sent = True
            meeting.save(update_fields=['reminder_sent'])

        # Auto-transition statuses
        for m in Meeting.objects.filter(status='scheduled'):
            if m.scheduled_at <= now <= m.ends_at:
                m.status = 'ongoing'
                m.save(update_fields=['status'])
            elif m.ends_at < now:
                m.status = 'completed'
                m.save(update_fields=['status'])

    except Exception as e:
        logger.warning(f'[NotifEngine] fire_pending_reminders error: {e}')


def _schedule_next(interval_seconds=60):
    """Re-schedule itself every interval_seconds using a daemon thread timer."""
    fire_pending_reminders()
    t = threading.Timer(interval_seconds, _schedule_next, args=[interval_seconds])
    t.daemon = True
    t.start()


def start_background_notifier():
    """Call once at app startup. Safe to call multiple times — only starts once."""
    global _timer_started
    with _lock:
        if _timer_started:
            return
        _timer_started = True
    t = threading.Timer(5, _schedule_next, args=[60])   # first fire after 5 s
    t.daemon = True
    t.start()
    logger.info('[NotifEngine] Background reminder engine started.')
