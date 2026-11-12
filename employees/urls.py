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

    # Fingerprint management
    path('<int:pk>/fingers/', views.finger_management, name='finger_management'),
    path('<int:pk>/fingers/set-max/', views.set_max_fingers, name='set_max_fingers'),
    path('fingers/<int:cred_pk>/delete/', views.delete_finger, name='delete_finger'),
    path('<int:pk>/fingers/delete-all/', views.delete_all_fingers, name='delete_all_fingers'),

    # Departments
    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_create, name='department_create'),
    path('departments/<int:pk>/edit/', views.department_edit, name='department_edit'),

    # Employee self portal
    path('dashboard/', views.employee_self_dashboard, name='employee_dashboard'),
]
