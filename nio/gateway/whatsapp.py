"""WhatsApp message loop via the Baileys bridge.

Polls the WhatsApp bridge HTTP server for incoming messages,
sends them to Ollama (or any model), runs NIO middleware,
sends responses back. No Hermes dependency.
"""

from __future__ import annotations

import json
import urllib.request

DEFAULT_BRIDGE = "http://localhost:3000"


def poll_messages(bridge_url: str = DEFAULT_BRIDGE, timeout: int = 30) -> list[dict]:
    """Long-poll the WhatsApp bridge for new messages.

    Returns list of message dicts: {chatId, text, sender, timestamp, media?}
    """
    try:
        req = urllib.request.Request(f"{bridge_url}/messages")
        with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
            data = json.loads(resp.read())
        if isinstance(data, list):
            return data
        return data.get("messages", [])
    except Exception:
        return []


def send_message(chat_id: str, text: str, bridge_url: str = DEFAULT_BRIDGE) -> bool:
    """Send a text message back through the WhatsApp bridge."""
    payload = json.dumps({
        "chatId": chat_id,
        "message": text,
    }).encode()

    try:
        req = urllib.request.Request(
            f"{bridge_url}/send",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_typing(chat_id: str, bridge_url: str = DEFAULT_BRIDGE):
    """Send typing indicator."""
    try:
        payload = json.dumps({"chatId": chat_id}).encode()
        req = urllib.request.Request(
            f"{bridge_url}/typing",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def check_bridge(bridge_url: str = DEFAULT_BRIDGE) -> bool:
    """Check if the WhatsApp bridge is running."""
    try:
        req = urllib.request.Request(f"{bridge_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False
