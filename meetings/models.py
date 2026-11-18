from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from employees.models import Employee


class Meeting(models.Model):
    STATUS_SCHEDULED  = 'scheduled'
    STATUS_ONGOING    = 'ongoing'
    STATUS_COMPLETED  = 'completed'
    STATUS_CANCELLED  = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_SCHEDULED,  'Scheduled'),
        (STATUS_ONGOING,    'Ongoing'),
        (STATUS_COMPLETED,  'Completed'),
        (STATUS_CANCELLED,  'Cancelled'),
    ]

    TYPE_INTERNAL   = 'internal'
    TYPE_CLIENT     = 'client'
    TYPE_STANDUP    = 'standup'
    TYPE_REVIEW     = 'review'
    TYPE_INTERVIEW  = 'interview'
    TYPE_OTHER      = 'other'
    TYPE_CHOICES = [
        (TYPE_INTERNAL,  'Internal Meeting'),
        (TYPE_CLIENT,    'Client Meeting'),
        (TYPE_STANDUP,   'Daily Standup'),
        (TYPE_REVIEW,    'Review / Retrospective'),
        (TYPE_INTERVIEW, 'Interview'),
        (TYPE_OTHER,     'Other'),
    ]

    # Core fields
    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    meeting_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_INTERNAL)
    agenda       = models.TextField(blank=True, help_text='Bullet-point agenda for the meeting')

    # Schedule
    scheduled_at  = models.DateTimeField()
    duration_mins = models.PositiveIntegerField(default=60, help_text='Duration in minutes')

    # Link / location
    meeting_link  = models.URLField(blank=True, help_text='Zoom / Google Meet / Teams link')
    location      = models.CharField(max_length=200, blank=True, help_text='Physical room or address')

    # People
    created_by  = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True,
        related_name='created_meetings'
    )
    attendees   = models.ManyToManyField(
        Employee, blank=True, related_name='meetings',
        through='MeetingAttendee'
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)

    # Notifications
    reminder_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_at']

    def __str__(self):
        return f"{self.title} — {self.scheduled_at.strftime('%d %b %Y %H:%M')}"

    @property
    def ends_at(self):
        from datetime import timedelta
        return self.scheduled_at + timedelta(minutes=self.duration_mins)

    @property
    def is_upcoming(self):
        return self.scheduled_at > timezone.now() and self.status == 'scheduled'

    @property
    def minutes_until(self):
        delta = self.scheduled_at - timezone.now()
        return int(delta.total_seconds() / 60)

    @property
    def status_color(self):
        return {
            'scheduled':  'primary',
            'ongoing':    'warning',
            'completed':  'success',
            'cancelled':  'danger',
        }.get(self.status, 'secondary')

    @property
    def type_icon(self):
        return {
            'internal':  'bi-people-fill',
            'client':    'bi-briefcase-fill',
            'standup':   'bi-lightning-fill',
            'review':    'bi-clipboard-check-fill',
            'interview': 'bi-person-check-fill',
            'other':     'bi-calendar-event-fill',
        }.get(self.meeting_type, 'bi-camera-video-fill')

    @property
    def type_color(self):
        return {
            'internal':  '#0077b6',
            'client':    '#7c3aed',
            'standup':   '#f59e0b',
            'review':    '#059669',
            'interview': '#0891b2',
            'other':     '#6b7280',
        }.get(self.meeting_type, '#6b7280')


class MeetingAttendee(models.Model):
    RSVP_PENDING  = 'pending'
    RSVP_ACCEPTED = 'accepted'
    RSVP_DECLINED = 'declined'
    RSVP_CHOICES = [
        (RSVP_PENDING,  'Pending'),
        (RSVP_ACCEPTED, 'Accepted'),
        (RSVP_DECLINED, 'Declined'),
    ]

    meeting    = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='attendee_set')
    employee   = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='meeting_attendances')
    rsvp       = models.CharField(max_length=10, choices=RSVP_CHOICES, default=RSVP_PENDING)
    joined_at  = models.DateTimeField(null=True, blank=True)
    notified   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['meeting', 'employee']
        ordering = ['employee__user__first_name']

    def __str__(self):
        return f"{self.employee} @ {self.meeting}"


class MeetingNotification(models.Model):
    """In-app notification record per attendee."""
    TYPE_INVITE   = 'invite'
    TYPE_REMINDER = 'reminder'
    TYPE_UPDATE   = 'update'
    TYPE_CANCEL   = 'cancel'
    TYPE_CHOICES = [
        (TYPE_INVITE,   'Meeting Invite'),
        (TYPE_REMINDER, '5-min Reminder'),
        (TYPE_UPDATE,   'Meeting Updated'),
        (TYPE_CANCEL,   'Meeting Cancelled'),
    ]

    employee       = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='meeting_notifications')
    meeting        = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_INVITE)
    message        = models.CharField(max_length=300)
    is_read        = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} → {self.employee}"
