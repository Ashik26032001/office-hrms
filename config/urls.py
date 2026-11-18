from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.http import HttpResponse
import os


def service_worker(request):
    """Serve service worker from static — must be at root path for full scope."""
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    with open(sw_path, 'r') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')


urlpatterns = [
    path('admin/',      admin.site.urls),
    path('accounts/',   include('accounts.urls')),
    path('dashboard/',  include('dashboard.urls')),
    path('employees/',  include('employees.urls')),
    path('attendance/', include('attendance.urls')),
    path('reports/',    include('reports.urls')),
    path('employee/',   include('employees.urls')),
    path('work/',       include('work_progress.urls')),
    path('meetings/',   include('meetings.urls')),
    path('ai/',         include('ai_assistant.urls')),

    # PWA
    path('sw.js',   service_worker,                                    name='service_worker'),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),

    path('', lambda request: redirect('login'), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
