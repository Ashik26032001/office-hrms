from django.urls import path
from . import views

urlpatterns = [
    # HR
    path('hr/projects/', views.hr_project_list, name='hr_project_list'),
    path('hr/projects/create/', views.hr_create_project, name='hr_create_project'),
    path('hr/projects/<int:pk>/edit/', views.hr_edit_project, name='hr_edit_project'),
    path('hr/projects/<int:pk>/', views.hr_project_detail, name='hr_project_detail'),
    path('hr/projects/<int:pk>/delete/', views.hr_delete_project, name='hr_delete_project'),
    # Employee
    path('my-projects/', views.employee_project_list, name='employee_project_list'),
    path('my-projects/<int:pk>/board/', views.employee_kanban, name='employee_kanban'),
    # AJAX
    path('task/<int:task_id>/status/', views.update_task_status, name='update_task_status'),
    path('task/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    path('task/<int:task_id>/edit/', views.edit_task, name='edit_task'),
]
