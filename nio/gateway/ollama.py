"""Ollama client for local model inference.

Talks to Ollama's API at localhost:11434 (or remote host).
Zero dependencies beyond stdlib.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gemma2"


def chat(
    message: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    history: Optional[list] = None,
) -> str:
    """Send a message to Ollama and return the response text.

    Args:
        message: User message
        system_prompt: System prompt (soul body)
        model: Model name (gemma2, gemma2:2b, llama3, etc.)
        host: Ollama API host
        history: Previous messages for multi-turn [{role, content}, ...]

    Returns:
        Assistant response text
    """
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": message})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    return data.get("message", {}).get("content", "")


def check_health(host: str = DEFAULT_HOST) -> bool:
    """Check if Ollama is running."""
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_models(host: str = DEFAULT_HOST) -> list[str]:
    """List available models on the Ollama instance."""
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []
