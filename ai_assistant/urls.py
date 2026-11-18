from django.urls import path
from . import views

urlpatterns = [
    path('',                        views.chat_view,       name='ai_chat'),
    path('send/',                   views.send_message,    name='ai_send'),
    path('new-session/',            views.new_session,     name='ai_new_session'),
    path('session/<int:session_id>/', views.session_history, name='ai_session_history'),
    path('status/',                 views.ollama_status,   name='ai_ollama_status'),
]
