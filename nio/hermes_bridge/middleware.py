"""NIO middleware for Hermes gateway events.

Handles: gateway:startup, session:start, agent:start, agent:end, command:*
Provides: soul injection, voice enforcement, anti-slop validation, metrics capture.
"""

from __future__ import annotations

import time
from typing import Any

# Session state tracked per active session
_active_sessions: dict[str, dict] = {}


async def handle(event_type: str, context: dict[str, Any]) -> Any:
    """Main event dispatcher called by the Hermes hook system."""
    handlers = {
        "gateway:startup": _on_gateway_startup,
        "session:start": _on_session_start,
        "session:end": _on_session_end,
        "agent:start": _on_agent_start,
        "agent:end": _on_agent_end,
    }

    if event_type.startswith("command:"):
        return await _on_command(event_type, context)

    handler = handlers.get(event_type)
    if handler:
        return await handler(context)


async def _on_gateway_startup(context: dict) -> None:
    """Load active soul + voice, init DB, start dash daemon if autostart."""
    from nio.core.db import init_db
    init_db()


async def _on_session_start(context: dict) -> None:
    """Create session row, resolve soul, inject soul + voice prompts."""
    from nio.core.metrics import create_session
    from nio.core.soul import get_active_soul, resolve_soul_with_inheritance
    from nio.core.voice import get_active_voice, load_voice

    # Resolve soul + voice (team mode overrides global)
    soul_id = ""
    soul_version = ""
    voice_id = ""
    voice_version = ""
    voice_ref = ""

    try:
        from nio.core.mode import (
            get_active_mode,
            get_effective_soul,
            get_effective_voice,
            get_team_id,
        )
        mode = get_active_mode()
        if mode == "team":
            soul_id, soul_version = get_effective_soul()
            voice_id, voice_version = get_effective_voice()
            voice_ref = f"{voice_id}@{voice_version}" if voice_id else ""
            context["team_id"] = get_team_id()
        else:
            raise ValueError("global mode")
    except Exception:
        # Global mode fallback
        soul_ref = get_active_soul()
        voice_ref = get_active_voice() or ""

        if soul_ref and "@" in soul_ref:
            soul_id, soul_version = soul_ref.split("@", 1)
        elif soul_ref:
            soul_id = soul_ref

        if voice_ref and "@" in voice_ref:
            voice_id, voice_version = voice_ref.split("@", 1)
        elif voice_ref:
            voice_id = voice_ref

    platform = context.get("platform", "cli")
    team_id = context.get("team_id", "")

    session_id = create_session(
        soul_id=soul_id,
        soul_version=soul_version,
        voice_id=voice_id,
        voice_version=voice_version,
        platform=platform,
        team_id=team_id,
    )

    # Resolve full soul prompt
    if soul_id:
        try:
            resolved = resolve_soul_with_inheritance(soul_id)
            # Inject into Hermes context for system prompt
            context["nio_system_prompt"] = resolved.get("body", "")
        except Exception:
            pass

    # Always register the session for turn tracking
    _active_sessions[session_id] = {
        "voice": None,
        "turn_index": 0,
        "session_id": session_id,
    }

    # Load voice for runtime use
    if voice_ref:
        voice = load_voice(voice_ref)
        if voice:
            _active_sessions[session_id]["voice"] = voice

    context["nio_session_id"] = session_id

    # Session resume: carry context from previous session
    try:
        import json as _json

        from nio.core.db import get_connection
        from nio.core.memory import get_session_context, summarize_session

        conn = get_connection()
        prev = conn.execute(
            "SELECT session_id FROM sessions WHERE ended_at IS NOT NULL "
            "ORDER BY ended_at DESC LIMIT 1"
        ).fetchone()

        if prev:
            prev_id = prev[0]
            summary = summarize_session(prev_id, conn=conn)
            session_ctx = get_session_context(last_n=3)

            conn.execute(
                "UPDATE sessions SET resumed_from = ?, context_snapshot = ? WHERE session_id = ?",
                (prev_id, _json.dumps(session_ctx), session_id),
            )
            conn.commit()

            context["nio_memory_context"] = (
                f"Previous session: {summary}\n"
                f"Total sessions: {session_ctx['session_count']}, "
                f"turns: {session_ctx['turn_count']}"
            )
        conn.close()
    except Exception:
        pass  # Memory system not yet initialized


async def _on_session_end(context: dict) -> None:
    """Mark session as ended, clean up active session state."""
    session_id = context.get("nio_session_id")
    if not session_id:
        return

    # Mark ended in DB
    try:
        from datetime import datetime, timezone

        from nio.core.db import get_connection
        conn = get_connection()
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE session_id = ? AND ended_at IS NULL",
            (datetime.now(timezone.utc).isoformat(), session_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    # Clean up memory
    _active_sessions.pop(session_id, None)


async def _on_agent_start(context: dict) -> None:
    """Record turn start time, user message, and classify task type."""
    session_id = context.get("nio_session_id")
    if session_id and session_id in _active_sessions:
        _active_sessions[session_id]["turn_start"] = time.time()
        user_msg = context.get("user_message", "")
        _active_sessions[session_id]["user_msg"] = user_msg

        # Classify task type on first turn
        if _active_sessions[session_id]["turn_index"] == 0:
            from nio.core.metrics import classify_task
            task_type = classify_task(user_msg)
            _active_sessions[session_id]["task_type"] = task_type
            # Update session row
            from nio.core.db import get_connection
            conn = get_connection()
            conn.execute(
                "UPDATE sessions SET task_type = ? WHERE session_id = ?",
                (task_type, session_id),
            )
            conn.commit()
            conn.close()


async def _on_agent_end(context: dict) -> None:
    """Validate output, compute slop score, record turn, emit websocket event."""
    from nio.core.metrics import record_turn
    from nio.core.voice import apply as voice_apply

    session_id = context.get("nio_session_id")
    if not session_id or session_id not in _active_sessions:
        return

    state = _active_sessions[session_id]
    agent_msg = context.get("agent_message", "")
    voice = state.get("voice")

    # Calculate latency
    turn_start = state.get("turn_start", time.time())
    latency_ms = int((time.time() - turn_start) * 1000)

    # Apply voice profile + anti-slop validation
    slop_score = 100.0
    violations = []
    if voice:
        result = voice_apply(voice, agent_msg)
        slop_score = result.score
        violations = [
            {"id": d.id, "tier": d.tier, "description": d.description, "matches": d.matches}
            for d in result.detections
        ]
    else:
        # Always run anti-slop even without a voice profile
        from nio.core.antislop import detect, score
        slop_score = score(agent_msg)
        for d in detect(agent_msg):
            violations.append({
                "id": d["id"], "tier": d["tier"],
                "description": d["description"], "matches": d.get("matches", []),
            })

    # Warn if below floor
    soul_floor = state.get("slop_score_floor", 92)
    if slop_score < soul_floor:
        _emit_slop_warning(session_id, slop_score, soul_floor, violations)

    # Record turn
    state["turn_index"] += 1
    record_turn(
        session_id=session_id,
        turn_index=state["turn_index"],
        user_msg=state.get("user_msg", ""),
        agent_msg=agent_msg,
        latency_ms=latency_ms,
        slop_score=slop_score,
        slop_violations=violations,
        tool_calls=context.get("tool_calls"),
        memory_hits=context.get("memory_hits", 0),
    )

    # Emit websocket event for dashboard
    _emit_dashboard_event(session_id, slop_score, latency_ms, violations)


async def _on_command(event_type: str, context: dict) -> Any:
    """Handle /nio-* slash commands in Hermes."""
    cmd = event_type.replace("command:", "")
    if cmd == "nio-status":
        from nio.core.soul import get_active_soul
        from nio.core.voice import get_active_voice
        return f"Soul: {get_active_soul() or 'none'}\nVoice: {get_active_voice() or 'none'}"
    elif cmd.startswith("nio-soul "):
        soul_id = cmd.replace("nio-soul ", "").strip()
        from nio.core.soul import set_active_soul
        set_active_soul(soul_id)
        return f"Switched to soul: {soul_id}"
    elif cmd == "nio-dash":
        import webbrowser
        webbrowser.open("http://localhost:4242")
        return "Opening dashboard..."
    return None


def _emit_slop_warning(session_id: str, score: float, floor: float, violations: list):
    """Log a slop warning (visible in Hermes output)."""
    violation_summary = ", ".join(
        f"{v['id']} ({v.get('count', len(v.get('matches', [])))})"
        for v in violations[:3]
    )
    print(f"[nio] slop-score {score:.0f}/100 (floor {floor:.0f})")
    if violation_summary:
        print(f"[nio] violations: {violation_summary}")
    print("[nio] see dashboard: http://localhost:4242")


def _emit_dashboard_event(session_id: str, slop_score: float, latency_ms: int, violations: list):
    """Emit a websocket event for the live dashboard."""
    try:
        import datetime

        from nio.dash.ws import broadcast_sync

        broadcast_sync({
            "type": "turn",
            "session_id": session_id,
            "slop_score": slop_score,
            "latency_ms": latency_ms,
            "violations": violations[:5],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
    except ImportError:
        pass  # Dashboard dependencies not installed (e.g., fastapi)
