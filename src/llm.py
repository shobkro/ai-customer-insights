"""One small interface over several FREE AI providers.

    ask_llm(system, user) -> str

Providers:
  ollama  - runs on your own laptop, 100% free, no key (https://ollama.com)
  gemini  - Google AI Studio free tier (needs GEMINI_API_KEY)
  groq    - Groq free tier, OpenAI-compatible API (needs GROQ_API_KEY)

Only `requests` is used, so there are no paid SDKs or extra dependencies.
"""
from __future__ import annotations

import time

import requests

from src import config


class LLMError(RuntimeError):
    pass


def _post(url: str, payload: dict, headers: dict | None = None, retries: int = 4) -> dict:
    """POST with simple retry/backoff - free tiers often return 429 (rate limit)."""
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, headers=headers or {}, timeout=180)
        except requests.ConnectionError as exc:
            raise LLMError(
                f"Cannot reach {url}. If using Ollama, is it running? (`ollama serve`)"
            ) from exc
        if resp.status_code in (429, 500, 502, 503):
            wait = 2 ** attempt * 5
            print(f"  rate-limited/busy ({resp.status_code}), waiting {wait}s ...")
            time.sleep(wait)
            continue
        if resp.status_code >= 400:
            raise LLMError(f"{resp.status_code}: {resp.text[:300]}")
        return resp.json()
    raise LLMError("Gave up after repeated rate limits. Try again later or use Ollama.")


def _ollama(system: str, user: str, json_mode: bool) -> str:
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": 0},
    }
    if json_mode:
        payload["format"] = "json"
    data = _post(f"{config.OLLAMA_URL}/api/chat", payload)
    return data["message"]["content"]


def _groq(system: str, user: str, json_mode: bool) -> str:
    if not config.GROQ_API_KEY:
        raise LLMError("Set GROQ_API_KEY in .env (free key at https://console.groq.com)")
    payload = {
        "model": config.GROQ_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post(
        "https://api.groq.com/openai/v1/chat/completions",
        payload,
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
    )
    return data["choices"][0]["message"]["content"]


def _gemini(system: str, user: str, json_mode: bool) -> str:
    if not config.GEMINI_API_KEY:
        raise LLMError("Set GEMINI_API_KEY in .env (free key at https://aistudio.google.com)")
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0},
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{config.GEMINI_MODEL}:generateContent")
    data = _post(url, payload, headers={"x-goog-api-key": config.GEMINI_API_KEY})
    return data["candidates"][0]["content"]["parts"][0]["text"]


PROVIDERS = {"ollama": _ollama, "groq": _groq, "gemini": _gemini}


def ask_llm(system: str, user: str, provider: str | None = None, json_mode: bool = True) -> str:
    provider = (provider or config.LLM_PROVIDER).lower()
    if provider not in PROVIDERS:
        raise LLMError(f"Unknown provider '{provider}'. Choose from {list(PROVIDERS)}.")
    return PROVIDERS[provider](system, user, json_mode)
