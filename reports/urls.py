from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_home, name='reports_home'),
    path('daily/', views.daily_report, name='daily_report'),
    path('daily/export/', views.export_daily_excel, name='export_daily_excel'),
    path('monthly/', views.monthly_report, name='monthly_report'),
]
