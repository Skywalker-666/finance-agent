"""Minimal client for any OpenAI-compatible chat API (Groq, Gemini, OpenAI, Ollama).

Configured by environment variables, never hard-coded:
  LLM_API_KEY   - required for online mode (kept server-side only)
  LLM_BASE_URL  - default: Groq's OpenAI-compatible endpoint
  LLM_MODEL     - default: openai/gpt-oss-120b
"""
from __future__ import annotations

import os

import httpx

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"


class LLMError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def chat(messages: list[dict], tools: list[dict] | None = None, timeout: float = 30.0) -> dict:
    """Send one chat-completions request and return the assistant message dict."""
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise LLMError("LLM_API_KEY is not set")
    base = os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    body: dict = {"model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
                  "messages": messages, "temperature": 0.2}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    try:
        r = httpx.post(f"{base}/chat/completions", json=body, timeout=timeout,
                       headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as e:
        raise LLMError(f"LLM request failed: {e.__class__.__name__}") from e
    if r.status_code != 200:
        # Never echo the key; only status and a short body snippet.
        raise LLMError(f"LLM returned HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]
