from django.urls import path
from . import views

urlpatterns = [
    path('',          views.admin_dashboard,         name='admin_dashboard'),
    path('settings/', views.settings_page,           name='settings_page'),
    path('settings/location/', views.get_current_location_api, name='get_location_api'),
]
