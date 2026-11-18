from django.urls import path
from . import views

urlpatterns = [
    # HR
    path('',                          views.hr_meeting_list,    name='hr_meeting_list'),
    path('create/',                   views.hr_create_meeting,  name='hr_create_meeting'),
    path('<int:pk>/',                 views.hr_meeting_detail,  name='hr_meeting_detail'),
    path('<int:pk>/edit/',            views.hr_edit_meeting,    name='hr_edit_meeting'),
    path('<int:pk>/cancel/',          views.hr_cancel_meeting,  name='hr_cancel_meeting'),
    path('<int:pk>/delete/',          views.hr_delete_meeting,  name='hr_delete_meeting'),
    # Employee
    path('my/',                       views.employee_meetings,  name='employee_meetings'),
    path('<int:pk>/rsvp/',            views.rsvp,               name='meeting_rsvp'),
    # Notifications (AJAX)
    path('notifications/poll/',       views.poll_notifications,     name='meeting_poll_notifications'),
    path('notifications/<int:nid>/read/', views.mark_notification_read, name='meeting_mark_read'),
    path('notifications/count/',      views.unread_count,           name='meeting_unread_count'),
    path('notifications/upcoming-json/', views.upcoming_meetings_json, name='meeting_upcoming_json'),
]
