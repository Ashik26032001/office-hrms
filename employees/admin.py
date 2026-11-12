from django.contrib import admin
from .models import Employee, Department, Shift


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_time', 'end_time', 'grace_period_minutes']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'get_full_name', 'department', 'designation', 'status']
    list_filter = ['department', 'status']
    search_fields = ['employee_id', 'user__first_name', 'user__last_name']
    readonly_fields = ['qr_token', 'qr_image']

    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Name'
