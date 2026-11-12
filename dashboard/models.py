from django.db import models


class CompanySettings(models.Model):
    """
    Singleton model — only one row ever exists.
    Stores company-wide settings including office geofence location.
    """
    company_name   = models.CharField(max_length=200, default='My Company')
    company_email  = models.EmailField(blank=True)
    company_phone  = models.CharField(max_length=20, blank=True)
    company_address = models.TextField(blank=True)

    # Office GPS location for geofencing
    office_latitude  = models.FloatField(default=10.0261)
    office_longitude = models.FloatField(default=76.3083)
    geofence_radius  = models.IntegerField(
        default=200,
        help_text='Allowed radius in metres from office centre'
    )
    geofence_enabled = models.BooleanField(
        default=True,
        help_text='If disabled, attendance is allowed from any location'
    )

    # Attendance settings
    work_start_time = models.TimeField(default='09:00')
    work_end_time   = models.TimeField(default='18:00')
    grace_minutes   = models.IntegerField(default=15)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company Settings'

    def __str__(self):
        return f"Settings — {self.company_name}"

    @classmethod
    def get(cls):
        """Always returns the single settings object, creates if missing."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
