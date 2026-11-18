"""
ollama_client.py
================
Thin wrapper around Ollama's HTTP API (http://localhost:11434).
Falls back gracefully when Ollama is not running.
"""

import httpx
import json
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE   = 'http://localhost:11434'
DEFAULT_MODEL = 'llama3.2'          # change to any model you have pulled
TIMEOUT       = 60                  # seconds


def is_ollama_available() -> bool:
    """Check if Ollama HTTP API is reachable."""
    try:
        r = httpx.get(f'{OLLAMA_BASE}/api/tags', timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_available_models() -> list[str]:
    """Return list of locally pulled model names."""
    try:
        r = httpx.get(f'{OLLAMA_BASE}/api/tags', timeout=3)
        if r.status_code == 200:
            return [m['name'] for m in r.json().get('models', [])]
    except Exception:
        pass
    return []


def chat(system_prompt: str, user_message: str, history: list[dict] = None, model: str = None) -> str:
    """
    Send a chat request to Ollama and return the response text.

    history: list of {'role': 'user'|'assistant', 'content': '...'} dicts
    Returns the assistant reply string, or raises on failure.
    """
    model = model or DEFAULT_MODEL

    messages = [{'role': 'system', 'content': system_prompt}]
    if history:
        messages.extend(history[-10:])   # keep last 10 turns for context
    messages.append({'role': 'user', 'content': user_message})

    payload = {
        'model':    model,
        'messages': messages,
        'stream':   False,
        'options': {
            'temperature': 0.3,   # lower = more factual
            'top_p':       0.9,
        },
    }

    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f'{OLLAMA_BASE}/api/chat', json=payload)
        r.raise_for_status()
        data = r.json()
        return data['message']['content']
