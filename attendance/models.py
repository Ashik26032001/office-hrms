from django.db import models
from django.utils import timezone
import uuid


class AttendanceEvent(models.Model):
    EVENT_IN  = 'IN'
    EVENT_OUT = 'OUT'
    EVENT_CHOICES = [(EVENT_IN, 'Check In'), (EVENT_OUT, 'Check Out')]

    METHOD_QR          = 'qr'
    METHOD_FACE        = 'face'
    METHOD_FINGERPRINT = 'fingerprint'
    METHOD_MANUAL      = 'manual'
    METHOD_CHOICES = [
        (METHOD_QR,          'QR Scan'),
        (METHOD_FACE,        'Face Recognition'),
        (METHOD_FINGERPRINT, 'Fingerprint'),
        (METHOD_MANUAL,      'Manual Entry'),
    ]

    employee     = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='attendance_events'
    )
    event_type   = models.CharField(max_length=3, choices=EVENT_CHOICES)
    timestamp    = models.DateTimeField(default=timezone.now)
    method       = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_QR)
    scanner_note = models.CharField(max_length=200, blank=True, default='Office Scanner')
    is_manual    = models.BooleanField(default=False)

    # Geofence data — stored with every scan for audit
    scan_latitude  = models.FloatField(null=True, blank=True)
    scan_longitude = models.FloatField(null=True, blank=True)
    location_valid = models.BooleanField(null=True, blank=True)  # True=inside office
    distance_metres = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.employee} - {self.event_type} [{self.method}] at {self.timestamp}"

    def local_time(self):
        return timezone.localtime(self.timestamp)


class WebAuthnChallenge(models.Model):
    """
    Temporarily stores a WebAuthn challenge during fingerprint
    registration and authentication flows.
    Deleted after use or expiry.
    """
    employee  = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='webauthn_challenges',
        null=True, blank=True
    )
    challenge = models.CharField(max_length=512)
    purpose   = models.CharField(
        max_length=20,
        choices=[('register', 'Register'), ('authenticate', 'Authenticate')],
        default='authenticate'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        """Challenge expires after 5 minutes."""
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(minutes=5)
