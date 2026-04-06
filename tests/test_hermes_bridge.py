"""Integration tests for the NIO Hermes bridge middleware.

Simulates the full 5-event pipeline and verifies:
- Session creation in DB
- Turn recording with slop scores
- Task-type classification
- Voice enforcement
"""

import asyncio
import json

import pytest

from nio.core import db as db_mod
from nio.core import metrics as metrics_mod
from nio.core import soul as soul_mod


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    """Use a temporary DB for each test."""
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = tmp_path / "test.db"
    db_mod.init_db()
    yield
    db_mod.DB_PATH = orig


# --- Middleware import ---

def test_middleware_import():
    from nio.hermes_bridge.middleware import handle
    assert callable(handle)


# --- Task-type classifier ---

def test_classify_coding():
    from nio.core.metrics import classify_task
    assert classify_task("implement a function that sorts users") == "coding"
    assert classify_task("write code for the API endpoint") == "coding"


def test_classify_debugging():
    from nio.core.metrics import classify_task
    assert classify_task("fix the bug in the login flow") == "debugging"
    assert classify_task("this is broken, debug it") == "debugging"


def test_classify_review():
    from nio.core.metrics import classify_task
    assert classify_task("review this PR") == "review"
    assert classify_task("code review for the auth module") == "review"


def test_classify_writing():
    from nio.core.metrics import classify_task
    assert classify_task("write a blog post about GTM") == "writing"
    assert classify_task("draft the README documentation") == "writing"


def test_classify_planning():
    from nio.core.metrics import classify_task
    assert classify_task("plan the architecture for v2") == "planning"
    assert classify_task("design the roadmap for Q3") == "planning"


def test_classify_general():
    from nio.core.metrics import classify_task
    assert classify_task("hello") == "general"
    assert classify_task("") == "general"


# --- Session and turn recording ---

def test_create_session():
    session_id = metrics_mod.create_session(
        soul_id="nio-core", soul_version="0.1.0",
        voice_id="shawn-builder", voice_version="1.0.0",
        platform="cli",
    )
    assert session_id
    conn = db_mod.get_connection()
    row = conn.execute("SELECT soul_id, platform FROM sessions WHERE session_id = ?",
                       (session_id,)).fetchone()
    conn.close()
    assert row[0] == "nio-core"
    assert row[1] == "cli"


def test_record_turn():
    session_id = metrics_mod.create_session(soul_id="nio-core", soul_version="0.1.0")
    turn_id = metrics_mod.record_turn(
        session_id=session_id,
        turn_index=1,
        user_msg="build a scoring model",
        agent_msg="I built the scoring model using SQLite and cron jobs.",
        latency_ms=1500,
        slop_score=94.5,
        slop_violations=[{"id": "quotation_overuse", "count": 1}],
    )
    assert turn_id

    conn = db_mod.get_connection()
    row = conn.execute("SELECT slop_score, latency_ms, user_msg FROM turns WHERE turn_id = ?",
                       (turn_id,)).fetchone()
    conn.close()
    assert row[0] == 94.5
    assert row[1] == 1500
    assert row[2] == "build a scoring model"


def test_slop_avg():
    session_id = metrics_mod.create_session(soul_id="nio-core", soul_version="0.1.0")
    for i, score in enumerate([90.0, 95.0, 85.0]):
        metrics_mod.record_turn(session_id=session_id, turn_index=i+1, slop_score=score)

    avg = metrics_mod.get_recent_slop_avg(hours=1)
    assert avg is not None
    assert abs(avg - 90.0) < 0.1


def test_query_metrics():
    session_id = metrics_mod.create_session(soul_id="nio-core", soul_version="0.1.0")
    for i in range(5):
        metrics_mod.record_turn(
            session_id=session_id, turn_index=i+1,
            slop_score=90.0 + i, latency_ms=1000 + i * 100,
        )

    result = metrics_mod.query_metrics(window="1h")
    assert result["session_count"] == 1
    assert result["turn_count"] == 5
    assert result["slop_avg"] > 0
    assert result["latency_p50"] > 0


# --- Full pipeline simulation ---

def test_full_pipeline(tmp_path):
    """Simulate gateway:startup -> session:start -> agent:start -> agent:end."""
    from nio.hermes_bridge.middleware import _active_sessions, handle

    orig_home = soul_mod.NIO_HOME
    soul_mod.NIO_HOME = tmp_path
    (tmp_path / "active").mkdir(parents=True, exist_ok=True)
    (tmp_path / "active" / "soul.txt").write_text("nio-core@0.1.0")

    loop = asyncio.new_event_loop()
    ctx = {"platform": "cli"}

    # 1. gateway:startup
    loop.run_until_complete(handle("gateway:startup", ctx))

    # 2. session:start
    loop.run_until_complete(handle("session:start", ctx))
    session_id = ctx.get("nio_session_id")
    assert session_id, "session:start should set nio_session_id in context"

    # Verify session row
    conn = db_mod.get_connection()
    row = conn.execute("SELECT soul_id FROM sessions WHERE session_id = ?",
                       (session_id,)).fetchone()
    conn.close()
    assert row is not None

    # 3. agent:start
    ctx["user_message"] = "implement a sorting function in Python"
    loop.run_until_complete(handle("agent:start", ctx))

    # 4. agent:end
    ctx["agent_message"] = "I built the sorting function. It uses quicksort with a pivot selection."
    loop.run_until_complete(handle("agent:end", ctx))

    # Verify turn row with slop score
    conn = db_mod.get_connection()
    turn = conn.execute(
        "SELECT slop_score, latency_ms, user_msg FROM turns WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    assert turn is not None
    assert turn[0] is not None  # slop_score populated
    assert turn[0] >= 0  # valid score
    assert turn[2] == "implement a sorting function in Python"

    # Clean up
    _active_sessions.clear()
    loop.close()
    soul_mod.NIO_HOME = orig_home


def test_pipeline_with_sloppy_output(tmp_path):
    """Verify sloppy agent output gets a low slop score."""
    from nio.hermes_bridge.middleware import _active_sessions, handle

    orig_home = soul_mod.NIO_HOME
    soul_mod.NIO_HOME = tmp_path
    (tmp_path / "active").mkdir(parents=True, exist_ok=True)
    (tmp_path / "active" / "soul.txt").write_text("nio-core@0.1.0")

    loop = asyncio.new_event_loop()
    ctx = {"platform": "cli"}

    loop.run_until_complete(handle("gateway:startup", ctx))
    loop.run_until_complete(handle("session:start", ctx))
    session_id = ctx["nio_session_id"]

    ctx["user_message"] = "write something"
    loop.run_until_complete(handle("agent:start", ctx))

    # Intentionally sloppy output
    ctx["agent_message"] = (
        "The uncomfortable truth is that this is a game changer. "
        "Let me be clear \u2014 no fluff, just chaos. Nada."
    )
    loop.run_until_complete(handle("agent:end", ctx))

    conn = db_mod.get_connection()
    turn = conn.execute(
        "SELECT slop_score, slop_violations FROM turns WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()

    assert turn[0] < 50, f"Sloppy output should score low, got {turn[0]}"
    violations = json.loads(turn[1])
    violation_ids = [v["id"] for v in violations]
    assert "authority_signaling" in violation_ids or "hype_words" in violation_ids

    _active_sessions.clear()
    loop.close()
    soul_mod.NIO_HOME = orig_home


# --- Command handling ---

def test_command_nio_status(tmp_path):
    from nio.hermes_bridge.middleware import handle

    orig_home = soul_mod.NIO_HOME
    soul_mod.NIO_HOME = tmp_path
    (tmp_path / "active").mkdir(parents=True, exist_ok=True)
    (tmp_path / "active" / "soul.txt").write_text("nio-core@0.1.0")

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(handle("command:nio-status", {}))
    assert "nio-core" in result
    loop.close()
    soul_mod.NIO_HOME = orig_home
