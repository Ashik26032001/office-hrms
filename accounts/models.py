from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_HR = 'hr'
    ROLE_EMPLOYEE = 'employee'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_HR, 'HR Manager'),
        (ROLE_EMPLOYEE, 'Employee'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_EMPLOYEE)
    phone = models.CharField(max_length=15, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    def is_admin_or_hr(self):
        return self.role in [self.ROLE_ADMIN, self.ROLE_HR]

    def is_employee_role(self):
        return self.role == self.ROLE_EMPLOYEE

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
