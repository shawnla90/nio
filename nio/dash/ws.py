"""WebSocket broadcast for live dashboard updates.

Phase 6 implementation. Middleware emits events here, dashboard subscribes.
"""

from __future__ import annotations

import asyncio
import json
from typing import Set

from fastapi import WebSocket

_connections: Set[WebSocket] = set()


async def connect(websocket: WebSocket):
    """Accept a new dashboard WebSocket connection."""
    await websocket.accept()
    _connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive
    except Exception:
        _connections.discard(websocket)


async def broadcast(event: dict):
    """Broadcast an event to all connected dashboard clients."""
    if not _connections:  # noqa: F823
        return
    message = json.dumps(event)
    dead = set()
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _connections -= dead


def broadcast_sync(event: dict):
    """Synchronous wrapper for broadcast (called from middleware)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast(event))
        else:
            loop.run_until_complete(broadcast(event))
    except RuntimeError:
        pass
