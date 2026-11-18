import json
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib import messages
from django.utils import timezone

from .models import ChatSession, ChatMessage
from .data_context import get_context_for_user, context_to_system_prompt
from .rule_engine import answer as rule_answer
from . import ollama_client

logger = logging.getLogger(__name__)


def login_required_custom(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Main Chat Page ────────────────────────────────────────────────────────────

@login_required_custom
def chat_view(request):
    """Render the chat UI."""
    # Get or create today's session
    session, _ = ChatSession.objects.get_or_create(
        user=request.user,
        created_at__date=timezone.localdate(),
        defaults={'user': request.user},
    )

    history = session.messages.order_by('created_at')
    ollama_up = ollama_client.is_ollama_available()
    models    = ollama_client.get_available_models() if ollama_up else []

    context = {
        'session':    session,
        'history':    history,
        'ollama_up':  ollama_up,
        'models':     models,
        'user_role':  request.user.role,
    }
    return render(request, 'ai_assistant/chat.html', context)


# ── AJAX: Send a message ──────────────────────────────────────────────────────

@login_required_custom
def send_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data     = json.loads(request.body)
        question = data.get('message', '').strip()
        model    = data.get('model', ollama_client.DEFAULT_MODEL)
        session_id = data.get('session_id')
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not question:
        return JsonResponse({'error': 'Empty message'}, status=400)

    # Get or create session
    if session_id:
        try:
            session = ChatSession.objects.get(pk=session_id, user=request.user)
        except ChatSession.DoesNotExist:
            session = ChatSession.objects.create(user=request.user)
    else:
        session = ChatSession.objects.create(user=request.user)

    # Save user message
    ChatMessage.objects.create(session=session, role='user', content=question)

    # Build DB context
    ctx           = get_context_for_user(request.user)
    system_prompt = context_to_system_prompt(ctx)

    # Build history (last 10 turns)
    history_msgs = list(
        session.messages.order_by('-created_at')[:20][::-1]
    )
    history = [{'role': m.role, 'content': m.content} for m in history_msgs[:-1]]

    # Try Ollama first, fall back to rule engine
    ollama_up = ollama_client.is_ollama_available()
    engine_used = 'rule'

    if ollama_up:
        try:
            reply = ollama_client.chat(
                system_prompt=system_prompt,
                user_message=question,
                history=history,
                model=model,
            )
            engine_used = 'ollama'
        except Exception as e:
            logger.warning(f'Ollama error, falling back to rule engine: {e}')
            reply = rule_answer(question, ctx)
    else:
        reply = rule_answer(question, ctx)

    # Save assistant reply
    ChatMessage.objects.create(session=session, role='assistant', content=reply)

    return JsonResponse({
        'reply':       reply,
        'session_id':  session.pk,
        'engine':      engine_used,
        'ollama_up':   ollama_up,
    })


# ── AJAX: New session ─────────────────────────────────────────────────────────

@login_required_custom
def new_session(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    session = ChatSession.objects.create(user=request.user)
    return JsonResponse({'session_id': session.pk})


# ── AJAX: Get session history ─────────────────────────────────────────────────

@login_required_custom
def session_history(request, session_id):
    try:
        session = ChatSession.objects.get(pk=session_id, user=request.user)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    messages_data = [
        {'role': m.role, 'content': m.content, 'time': m.created_at.isoformat()}
        for m in session.messages.order_by('created_at')
    ]
    return JsonResponse({'messages': messages_data})


# ── AJAX: Ollama status ───────────────────────────────────────────────────────

@login_required_custom
def ollama_status(request):
    up     = ollama_client.is_ollama_available()
    models = ollama_client.get_available_models() if up else []
    return JsonResponse({'available': up, 'models': models})
