from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from employees.models import Employee


class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_projects')
    members = models.ManyToManyField(Employee, blank=True, related_name='projects')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def task_count(self):
        return self.tasks.count()

    def tasks_by_status(self):
        statuses = ['todo', 'open', 'under_review', 'done']
        return {s: self.tasks.filter(status=s).count() for s in statuses}

    def on_time_accuracy(self):
        """Percentage of tasks that are either done before/on deadline or still within deadline."""
        total = self.tasks.count()
        if total == 0:
            return 100
        today = timezone.localdate()
        on_time = 0
        for task in self.tasks.all():
            if task.end_date is None:
                on_time += 1
            elif task.status == 'done':
                # completed — count as on-time if end_date >= date completed_at (we use updated_at as proxy)
                if task.updated_at.date() <= task.end_date:
                    on_time += 1
            else:
                # not done — on time if deadline not yet passed
                if task.end_date >= today:
                    on_time += 1
        return round(on_time / total * 100)


class Task(models.Model):
    STATUS_TODO = 'todo'
    STATUS_OPEN = 'open'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [
        (STATUS_TODO, 'To Do'),
        (STATUS_OPEN, 'Open'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_DONE, 'Done'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TODO)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def is_overdue(self):
        if self.end_date and self.status != 'done':
            return self.end_date < timezone.localdate()
        return False

    def status_color(self):
        return {
            'todo': 'secondary',
            'open': 'primary',
            'under_review': 'warning',
            'done': 'success',
        }.get(self.status, 'secondary')

    def priority_color(self):
        return {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger',
        }.get(self.priority, 'secondary')
