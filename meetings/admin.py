from django.contrib import admin
from .models import Meeting, MeetingAttendee, MeetingNotification


class MeetingAttendeeInline(admin.TabularInline):
    model = MeetingAttendee
    extra = 0
    fields = ['employee', 'rsvp', 'notified', 'joined_at']
    readonly_fields = ['joined_at']


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display  = ['title', 'meeting_type', 'scheduled_at', 'duration_mins', 'status', 'created_by']
    list_filter   = ['status', 'meeting_type', 'scheduled_at']
    search_fields = ['title', 'description']
    inlines       = [MeetingAttendeeInline]
    date_hierarchy = 'scheduled_at'


@admin.register(MeetingAttendee)
class MeetingAttendeeAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'employee', 'rsvp', 'notified']
    list_filter  = ['rsvp', 'notified']


@admin.register(MeetingNotification)
class MeetingNotificationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'meeting', 'notification_type', 'is_read', 'created_at']
    list_filter  = ['notification_type', 'is_read']
