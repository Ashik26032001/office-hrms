from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from .models import Project, Task
from .forms import ProjectForm, TaskForm
from employees.models import Employee
import json


def hr_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        if not request.user.is_admin_or_hr():
            messages.error(request, 'Access denied.')
            return redirect('/employee/dashboard/')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_redirect(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── HR: Project List ────────────────────────────────────────────────────────

@hr_required
def hr_project_list(request):
    projects = Project.objects.prefetch_related('tasks', 'members').all()
    today = timezone.localdate()
    project_data = []
    for p in projects:
        tasks = p.tasks.all()
        total = tasks.count()
        project_data.append({
            'project': p,
            'total': total,
            'todo': tasks.filter(status='todo').count(),
            'open': tasks.filter(status='open').count(),
            'under_review': tasks.filter(status='under_review').count(),
            'done': tasks.filter(status='done').count(),
            'overdue': tasks.filter(end_date__lt=today).exclude(status='done').count(),
            'accuracy': p.on_time_accuracy(),
            'members_count': p.members.count(),
        })
    context = {
        'project_data': project_data,
        'total_projects': projects.count(),
        'total_tasks': Task.objects.count(),
        'total_done': Task.objects.filter(status='done').count(),
        'total_overdue': Task.objects.filter(end_date__lt=today).exclude(status='done').count(),
    }
    return render(request, 'work_progress/hr_project_list.html', context)


# ─── HR: Create Project ───────────────────────────────────────────────────────

@hr_required
def hr_create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m()
            messages.success(request, f'Project "{project.name}" created successfully!')
            return redirect('hr_project_list')
    else:
        form = ProjectForm()
    return render(request, 'work_progress/project_form.html', {'form': form, 'action': 'Create'})


# ─── HR: Edit Project ─────────────────────────────────────────────────────────

@hr_required
def hr_edit_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'Project "{project.name}" updated!')
            return redirect('hr_project_list')
    else:
        form = ProjectForm(instance=project)
    return render(request, 'work_progress/project_form.html', {'form': form, 'action': 'Edit', 'project': project})


# ─── HR: Project Detail (all tasks) ──────────────────────────────────────────

@hr_required
def hr_project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    tasks = project.tasks.select_related('assigned_to__user', 'created_by').all()
    today = timezone.localdate()
    context = {
        'project': project,
        'tasks': tasks,
        'todo_tasks': tasks.filter(status='todo'),
        'open_tasks': tasks.filter(status='open'),
        'review_tasks': tasks.filter(status='under_review'),
        'done_tasks': tasks.filter(status='done'),
        'today': today,
        'accuracy': project.on_time_accuracy(),
    }
    return render(request, 'work_progress/hr_project_detail.html', context)


# ─── HR: Delete Project ───────────────────────────────────────────────────────

@hr_required
def hr_delete_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f'Project "{name}" deleted.')
        return redirect('hr_project_list')
    return render(request, 'work_progress/project_confirm_delete.html', {'project': project})


# ─── Employee: My Projects ────────────────────────────────────────────────────

@login_required_redirect
def employee_project_list(request):
    try:
        employee = request.user.employee_profile
    except Exception:
        messages.error(request, 'No employee profile found.')
        return redirect('/employee/dashboard/')
    projects = employee.projects.filter(is_active=True).prefetch_related('tasks')
    today = timezone.localdate()
    project_data = []
    for p in projects:
        my_tasks = p.tasks.filter(assigned_to=employee)
        all_tasks = p.tasks.all()
        project_data.append({
            'project': p,
            'my_tasks': my_tasks.count(),
            'my_todo': my_tasks.filter(status='todo').count(),
            'my_open': my_tasks.filter(status='open').count(),
            'my_review': my_tasks.filter(status='under_review').count(),
            'my_done': my_tasks.filter(status='done').count(),
            'overdue': my_tasks.filter(end_date__lt=today).exclude(status='done').count(),
        })
    return render(request, 'work_progress/employee_project_list.html', {
        'project_data': project_data,
        'employee': employee,
    })


# ─── Employee: Kanban Board ───────────────────────────────────────────────────

@login_required_redirect
def employee_kanban(request, pk):
    try:
        employee = request.user.employee_profile
    except Exception:
        employee = None

    project = get_object_or_404(Project, pk=pk)

    # HR/Admin can view any project; employee must be a member
    if not request.user.is_admin_or_hr():
        if employee is None or employee not in project.members.all():
            messages.error(request, 'You are not a member of this project.')
            return redirect('employee_project_list')

    tasks = project.tasks.select_related('assigned_to__user').all()

    if request.method == 'POST':
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.created_by = request.user
            task.status = 'todo'
            task.save()
            messages.success(request, f'Task "{task.title}" created!')
            return redirect('employee_kanban', pk=pk)
    else:
        form = TaskForm(project=project)

    context = {
        'project': project,
        'form': form,
        'todo_tasks': tasks.filter(status='todo'),
        'open_tasks': tasks.filter(status='open'),
        'review_tasks': tasks.filter(status='under_review'),
        'done_tasks': tasks.filter(status='done'),
        'employee': employee if not request.user.is_admin_or_hr() else None,
    }
    return render(request, 'work_progress/kanban_board.html', context)


# ─── AJAX: Update task status (drag & drop) ───────────────────────────────────

@login_required_redirect
def update_task_status(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    task = get_object_or_404(Task, pk=task_id)

    # Only assigned employee, HR, or admin can move tasks
    if not request.user.is_admin_or_hr():
        try:
            emp = request.user.employee_profile
        except Exception:
            return JsonResponse({'error': 'Forbidden'}, status=403)
        if task.project not in emp.projects.all():
            return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    valid = ['todo', 'open', 'under_review', 'done']
    if new_status not in valid:
        return JsonResponse({'error': 'Invalid status'}, status=400)

    task.status = new_status
    task.save(update_fields=['status', 'updated_at'])

    return JsonResponse({
        'success': True,
        'task_id': task.pk,
        'new_status': new_status,
        'is_overdue': task.is_overdue(),
    })


# ─── AJAX: Delete Task ────────────────────────────────────────────────────────

@login_required_redirect
def delete_task(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    task = get_object_or_404(Task, pk=task_id)
    if not request.user.is_admin_or_hr() and task.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    task.delete()
    return JsonResponse({'success': True})


# ─── AJAX: Edit Task ──────────────────────────────────────────────────────────

@login_required_redirect
def edit_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if not request.user.is_admin_or_hr() and task.created_by != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, project=task.project)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'title': task.title})
        return JsonResponse({'error': str(form.errors)}, status=400)

    # GET: return task data for modal
    return JsonResponse({
        'id': task.pk,
        'title': task.title,
        'description': task.description,
        'priority': task.priority,
        'start_date': task.start_date.isoformat() if task.start_date else '',
        'end_date': task.end_date.isoformat() if task.end_date else '',
        'assigned_to': task.assigned_to_id or '',
        'status': task.status,
    })
