from django.urls import path
from . import views

urlpatterns = [
    # Admin/HR Employee Management
    path('', views.employee_list, name='employee_list'),
    path('add/', views.employee_create, name='employee_create'),
    path('<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('<int:pk>/detail/', views.employee_detail, name='employee_detail'),
    path('<int:pk>/delete/', views.employee_delete, name='employee_delete'),
    path('<int:pk>/regenerate-qr/', views.regenerate_qr, name='regenerate_qr'),

    # Departments
    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_create, name='department_create'),
    path('departments/<int:pk>/edit/', views.department_edit, name='department_edit'),

    # Employee self portal
    path('dashboard/', views.employee_self_dashboard, name='employee_dashboard'),
]
