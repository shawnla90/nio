"""Session and turn metrics capture + query surface."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

NIO_HOME = Path.home() / ".nio"

# Task-type classifier: keyword/regex table
_TASK_PATTERNS: list[tuple[str, list[str]]] = [
    ("debugging", ["fix", "debug", "broken", "failing", "crash", "exception", "stack trace",
                   "not working", "issue", "problem with", "bug"]),
    ("coding", ["implement", "write code", "function", "class ", "def ", "error",
                "traceback", "import", "module", "refactor", "compile", "build"]),
    ("review", ["review", "PR", "pull request", "code review", "LGTM", "approve",
                "feedback on", "check this", "look at this"]),
    ("writing", ["write", "draft", "blog", "post", "article", "copy", "content",
                 "readme", "documentation", "docs"]),
    ("planning", ["plan", "design", "architect", "strategy", "roadmap", "scope",
                  "spec", "RFC", "proposal", "approach"]),
]


def classify_task(user_msg: str) -> str:
    """Classify a user message into a task type using keyword matching.

    Returns: coding, debugging, review, writing, planning, or general.
    """
    if not user_msg:
        return "general"
    lower = user_msg.lower()
    scores: dict[str, int] = {}
    for task_type, keywords in _TASK_PATTERNS:
        count = sum(1 for kw in keywords if kw.lower() in lower)
        if count > 0:
            scores[task_type] = count
    if not scores:
        return "general"
    return max(scores, key=scores.get)


def _parse_window(window: str) -> timedelta:
    """Parse a window string like '7d', '24h', '30d' into a timedelta."""
    unit = window[-1]
    value = int(window[:-1])
    if unit == "d":
        return timedelta(days=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "m":
        return timedelta(minutes=value)
    return timedelta(days=7)


def create_session(
    soul_id: str = "",
    soul_version: str = "",
    voice_id: str = "",
    voice_version: str = "",
    platform: str = "cli",
    team_id: str = "",
) -> str:
    """Create a new session row and return the session_id."""
    from nio.core.db import get_connection

    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """INSERT INTO sessions (session_id, started_at, soul_id, soul_version,
           voice_id, voice_version, platform, team_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, datetime.utcnow().isoformat(), soul_id, soul_version,
         voice_id, voice_version, platform, team_id),
    )
    conn.commit()
    conn.close()
    return session_id


def end_session(session_id: str):
    """Mark a session as ended."""
    from nio.core.db import get_connection

    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET ended_at = ? WHERE session_id = ?",
        (datetime.utcnow().isoformat(), session_id),
    )
    conn.commit()
    conn.close()


def record_turn(
    session_id: str,
    turn_index: int,
    user_msg: str = "",
    agent_msg: str = "",
    latency_ms: int = 0,
    slop_score: float = 100.0,
    slop_violations: Optional[list] = None,
    tool_calls: Optional[list] = None,
    memory_hits: int = 0,
    user_signal: int = 0,
):
    """Record a single turn's metrics."""
    import json
    from nio.core.db import get_connection

    turn_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """INSERT INTO turns (turn_id, session_id, turn_index, user_msg, agent_msg,
           latency_ms, slop_score, slop_violations, tool_calls, memory_hits,
           user_signal, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            turn_id, session_id, turn_index, user_msg, agent_msg,
            latency_ms, slop_score,
            json.dumps(slop_violations or []),
            json.dumps(tool_calls or []),
            memory_hits, user_signal,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return turn_id


def get_recent_slop_avg(hours: int = 24) -> Optional[float]:
    """Get average slop score for the last N hours."""
    from nio.core.db import get_connection

    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT AVG(slop_score) FROM turns WHERE created_at > ? AND slop_score IS NOT NULL",
        (cutoff,),
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None


def query_metrics(
    window: str = "7d",
    soul_id: Optional[str] = None,
    task_type: Optional[str] = None,
) -> dict:
    """Query aggregate metrics over a time window."""
    from nio.core.db import get_connection

    cutoff = (datetime.utcnow() - _parse_window(window)).isoformat()
    conn = get_connection()

    base_query = """
        SELECT
            COUNT(DISTINCT t.session_id) as session_count,
            COUNT(t.turn_id) as turn_count,
            AVG(t.slop_score) as slop_avg,
            AVG(t.latency_ms) as latency_avg,
            AVG(t.user_signal) as signal_avg
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.created_at > ?
    """
    params = [cutoff]

    if soul_id:
        base_query += " AND s.soul_id = ?"
        params.append(soul_id)
    if task_type:
        base_query += " AND s.task_type = ?"
        params.append(task_type)

    row = conn.execute(base_query, params).fetchone()

    # Get percentiles for latency
    latencies = conn.execute(
        "SELECT latency_ms FROM turns t JOIN sessions s ON t.session_id = s.session_id "
        "WHERE t.created_at > ? AND t.latency_ms > 0 ORDER BY t.latency_ms",
        (cutoff,),
    ).fetchall()
    conn.close()

    latency_values = [r[0] for r in latencies]
    p50 = _percentile(latency_values, 50)
    p95 = _percentile(latency_values, 95)

    return {
        "session_count": row[0] or 0,
        "turn_count": row[1] or 0,
        "slop_avg": row[2] or 0.0,
        "latency_avg": row[3] or 0.0,
        "latency_p50": p50,
        "latency_p95": p95,
        "signal_avg": row[4] or 0.0,
    }


def query_team_metrics(team_id: str, window: str = "7d") -> dict:
    """Query team-wide metrics. Stub for v1."""
    return {"team_id": team_id, "members": []}


def export_metrics(format: str = "json", window: str = "30d"):
    """Export raw metrics data."""
    import json as json_mod
    from nio.core.db import get_connection

    cutoff = (datetime.utcnow() - _parse_window(window)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM turns WHERE created_at > ? ORDER BY created_at",
        (cutoff,),
    ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM turns LIMIT 0").description]
    conn.close()

    data = [dict(zip(cols, row)) for row in rows]
    print(json_mod.dumps(data, indent=2, default=str))


def _percentile(sorted_values: list, pct: int) -> float:
    if not sorted_values:
        return 0.0
    idx = int(len(sorted_values) * pct / 100)
    idx = min(idx, len(sorted_values) - 1)
    return float(sorted_values[idx])
