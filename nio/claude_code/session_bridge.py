"""Claude Code session bridge.

Tracks Claude Code sessions in the same nio.db used by Hermes sessions.
Runs anti-slop scoring on each recorded turn.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional


def start_cc_session(
    soul_id: str = "",
    soul_version: str = "",
    voice_id: str = "",
    voice_version: str = "",
    team_id: str = "",
) -> str:
    """Start a new Claude Code session.

    Creates a session row with platform='claude_code' and returns the session_id.
    If soul/voice not specified, reads from active pointers.
    """
    from nio.core.db import get_connection
    from nio.core.soul import get_active_soul
    from nio.core.voice import get_active_voice

    if not soul_id:
        ref = get_active_soul() or ""
        if "@" in ref:
            soul_id, soul_version = ref.split("@", 1)
        else:
            soul_id = ref

    if not voice_id:
        ref = get_active_voice() or ""
        if "@" in ref:
            voice_id, voice_version = ref.split("@", 1)
        else:
            voice_id = ref

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    conn.execute(
        """INSERT INTO sessions
           (session_id, started_at, soul_id, soul_version, voice_id, voice_version, platform, team_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, now, soul_id, soul_version, voice_id, voice_version, "claude_code", team_id),
    )
    conn.commit()
    conn.close()

    return session_id


def record_cc_turn(
    session_id: str,
    user_msg: str,
    agent_msg: str,
    turn_index: Optional[int] = None,
    latency_ms: int = 0,
    tool_calls: Optional[list] = None,
) -> dict:
    """Record a turn in a Claude Code session.

    Runs anti-slop scoring on the agent message and stores the result.
    Returns turn details including slop score and violations.
    """
    import json

    from nio.core.antislop import detect, score
    from nio.core.db import get_connection

    slop_score = score(agent_msg)
    violations = []
    for d in detect(agent_msg):
        violations.append({
            "id": d["id"],
            "tier": d["tier"],
            "description": d["description"],
            "matches": d.get("matches", []),
        })

    if turn_index is None:
        conn = get_connection()
        row = conn.execute(
            "SELECT MAX(turn_index) FROM turns WHERE session_id = ?", (session_id,)
        ).fetchone()
        turn_index = (row[0] or 0) + 1 if row else 1
        conn.close()

    turn_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    conn.execute(
        """INSERT INTO turns
           (turn_id, session_id, turn_index, user_msg, agent_msg,
            latency_ms, slop_score, slop_violations, tool_calls, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            turn_id, session_id, turn_index, user_msg, agent_msg,
            latency_ms, slop_score, json.dumps(violations),
            json.dumps(tool_calls or []), now,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "turn_id": turn_id,
        "turn_index": turn_index,
        "slop_score": slop_score,
        "violations": violations,
    }


def end_cc_session(session_id: str) -> dict:
    """End a Claude Code session.

    Sets ended_at, classifies task type from first turn, returns summary.
    """
    from nio.core.db import get_connection
    from nio.core.metrics import classify_task

    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()

    # Classify from first user message
    first = conn.execute(
        "SELECT user_msg FROM turns WHERE session_id = ? AND user_msg != '' ORDER BY turn_index LIMIT 1",
        (session_id,),
    ).fetchone()
    task_type = classify_task(first[0]) if first else "general"

    conn.execute(
        "UPDATE sessions SET ended_at = ?, task_type = ? WHERE session_id = ?",
        (now, task_type, session_id),
    )
    conn.commit()

    # Build summary
    stats = conn.execute(
        "SELECT COUNT(*), AVG(slop_score) FROM turns WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()

    turn_count = stats[0] or 0
    slop_avg = stats[1]

    return {
        "session_id": session_id,
        "ended_at": now,
        "task_type": task_type,
        "turn_count": turn_count,
        "slop_avg": round(slop_avg, 1) if slop_avg is not None else None,
    }


def get_cc_status() -> dict:
    """Get status of the most recent Claude Code session."""
    from nio.core.db import get_connection

    conn = get_connection()
    row = conn.execute(
        """SELECT session_id, started_at, ended_at, soul_id, soul_version, task_type
           FROM sessions WHERE platform = 'claude_code'
           ORDER BY started_at DESC LIMIT 1"""
    ).fetchone()

    if not row:
        conn.close()
        return {"active": False, "message": "No Claude Code sessions found"}

    session_id, started_at, ended_at, soul_id, soul_version, task_type = row

    stats = conn.execute(
        "SELECT COUNT(*), AVG(slop_score) FROM turns WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()

    return {
        "active": ended_at is None,
        "session_id": session_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "soul_id": soul_id,
        "soul_version": soul_version,
        "task_type": task_type,
        "turn_count": stats[0] or 0,
        "slop_avg": round(stats[1], 1) if stats[1] is not None else None,
    }


def get_cc_context() -> dict:
    """Get full context for current Claude Code session including memory."""
    from nio.core.memory import get_session_context
    from nio.core.mode import get_active_mode, get_effective_soul, get_effective_voice

    mode = get_active_mode()
    soul_id, soul_version = get_effective_soul()
    voice_id, voice_version = get_effective_voice()

    try:
        session_ctx = get_session_context(last_n=3)
    except Exception:
        session_ctx = {"session_count": 0, "turn_count": 0, "memory_facts": []}

    return {
        "mode": mode,
        "soul": f"{soul_id}@{soul_version}" if soul_id else "none",
        "voice": f"{voice_id}@{voice_version}" if voice_id else "none",
        "session_count": session_ctx.get("session_count", 0),
        "turn_count": session_ctx.get("turn_count", 0),
        "memory_facts": session_ctx.get("memory_facts", []),
        "last_session": session_ctx.get("last_session_summary", ""),
    }
