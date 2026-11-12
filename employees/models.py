import uuid
import qrcode
import io
from django.db import models
from django.core.files.base import ContentFile
from accounts.models import CustomUser


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Shift(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_period_minutes = models.IntegerField(default=15)

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"


class Employee(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name='employee_profile'
    )
    employee_id  = models.CharField(max_length=20, unique=True)
    department   = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, related_name='employees'
    )
    shift        = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    designation  = models.CharField(max_length=100)
    joining_date = models.DateField()
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    photo        = models.ImageField(upload_to='employee_photos/', blank=True, null=True)

    # QR token
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_image = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    # ── FACE RECOGNITION ──────────────────────────────────────────────────────
    # Stores the face photo used for recognition (can be same as photo or separate)
    face_photo = models.ImageField(
        upload_to='face_photos/', blank=True, null=True,
        help_text='Clear front-facing photo for face recognition'
    )
    face_enrolled = models.BooleanField(default=False)

    # ── WEBAUTHN FINGERPRINT ──────────────────────────────────────────────────
    # Stores the WebAuthn credential ID and public key (base64 encoded)
    webauthn_credential_id = models.TextField(blank=True, null=True)
    webauthn_public_key    = models.TextField(blank=True, null=True)
    webauthn_sign_count    = models.BigIntegerField(default=0)
    webauthn_enrolled      = models.BooleanField(default=False)
    # Max fingers allowed (admin sets this per employee, default 3)
    max_fingers_allowed    = models.IntegerField(default=3)

    def generate_qr(self):
        """Generate QR code image containing the secure token."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(str(self.qr_token))
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1e3a5f", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        filename = f"qr_{self.employee_id}.png"
        self.qr_image.save(filename, ContentFile(buffer.read()), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new or not self.qr_image:
            self.generate_qr()
            super().save(update_fields=['qr_image'])

    def get_full_name(self):
        return self.user.get_full_name() or self.user.username

    def __str__(self):
        return f"{self.employee_id} - {self.get_full_name()}"

    class Meta:
        ordering = ['employee_id']


class FingerCredential(models.Model):
    """
    Stores one WebAuthn credential per finger.
    Each employee can have up to max_fingers_allowed credentials.
    Admin can delete/reset individual fingers.
    """
    FINGER_CHOICES = [
        ('right_thumb',  'Right Thumb'),
        ('right_index',  'Right Index'),
        ('right_middle', 'Right Middle'),
        ('left_thumb',   'Left Thumb'),
        ('left_index',   'Left Index'),
        ('left_middle',  'Left Middle'),
        ('any',          'Any Finger'),
    ]

    employee       = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='finger_credentials'
    )
    finger_label   = models.CharField(
        max_length=20, choices=FINGER_CHOICES, default='any'
    )
    credential_id  = models.TextField(unique=True)
    public_key     = models.TextField()
    sign_count     = models.BigIntegerField(default=0)
    device_info    = models.CharField(max_length=200, blank=True,
                                       help_text='e.g. iPhone 14, Samsung Galaxy')
    enrolled_at    = models.DateTimeField(auto_now_add=True)
    last_used_at   = models.DateTimeField(null=True, blank=True)
    is_active      = models.BooleanField(default=True)

    class Meta:
        ordering = ['enrolled_at']

    def __str__(self):
        return f"{self.employee.employee_id} — {self.get_finger_label_display()}"
