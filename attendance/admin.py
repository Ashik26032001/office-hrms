from django.contrib import admin
from .models import AttendanceEvent


@admin.register(AttendanceEvent)
class AttendanceEventAdmin(admin.ModelAdmin):
    list_display = ['employee', 'event_type', 'timestamp', 'scanner_note', 'is_manual']
    list_filter = ['event_type', 'is_manual', 'timestamp']
    search_fields = ['employee__employee_id', 'employee__user__first_name', 'employee__user__last_name']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp']
