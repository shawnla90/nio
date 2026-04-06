"""Tests for Claude Code session bridge."""

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "nio.db"
    import nio.core.db as db_mod
    def patched():
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    monkeypatch.setattr(db_mod, "get_connection", patched)
    db_mod.init_db()
    return db_path


def test_start_cc_session(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session
    session_id = start_cc_session()
    assert session_id
    assert len(session_id) == 36  # UUID format


def test_start_session_creates_row(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session
    import nio.core.db as db_mod

    session_id = start_cc_session()
    conn = db_mod.get_connection()
    row = conn.execute(
        "SELECT platform, ended_at FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()

    assert row[0] == "claude_code"
    assert row[1] is None  # Not ended yet


def test_record_cc_turn(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session, record_cc_turn

    session_id = start_cc_session()
    result = record_cc_turn(session_id, "fix the bug", "I fixed the validation logic.")

    assert result["turn_index"] == 1
    assert result["slop_score"] >= 0
    assert result["slop_score"] <= 100
    assert isinstance(result["violations"], list)


def test_record_turn_detects_slop(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session, record_cc_turn

    session_id = start_cc_session()
    result = record_cc_turn(
        session_id,
        "write something",
        "The uncomfortable truth is this game-changer unleashes the revolutionary power of cutting-edge solutions."
    )

    assert result["slop_score"] < 80
    assert len(result["violations"]) > 0


def test_record_multiple_turns(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session, record_cc_turn

    session_id = start_cc_session()
    r1 = record_cc_turn(session_id, "first", "first response")
    r2 = record_cc_turn(session_id, "second", "second response")

    assert r1["turn_index"] == 1
    assert r2["turn_index"] == 2


def test_end_cc_session(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session, record_cc_turn, end_cc_session

    session_id = start_cc_session()
    record_cc_turn(session_id, "fix auth", "Updated token validation.")
    result = end_cc_session(session_id)

    assert result["session_id"] == session_id
    assert result["ended_at"] is not None
    assert result["turn_count"] == 1
    assert result["task_type"] in ["debugging", "coding", "review", "writing", "planning", "general"]


def test_get_cc_status_no_sessions(tmp_db):
    from nio.claude_code.session_bridge import get_cc_status

    status = get_cc_status()
    assert status["active"] is False


def test_get_cc_status_active(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session, get_cc_status

    start_cc_session()
    status = get_cc_status()
    assert status["active"] is True
    assert status["session_id"]


def test_get_cc_status_after_end(tmp_db):
    from nio.claude_code.session_bridge import start_cc_session, end_cc_session, get_cc_status

    session_id = start_cc_session()
    end_cc_session(session_id)
    status = get_cc_status()
    assert status["active"] is False


def test_get_cc_context(tmp_db):
    from nio.claude_code.session_bridge import get_cc_context

    ctx = get_cc_context()
    assert "mode" in ctx
    assert "soul" in ctx
    assert "voice" in ctx
    assert "session_count" in ctx


def test_handoff_import(tmp_db, tmp_path, monkeypatch):
    """Test importing Claude handoffs into NIO DB."""
    handoffs_dir = tmp_path / "handoffs"
    handoffs_dir.mkdir()
    (handoffs_dir / "2026-04-05_test.md").write_text(
        "# Handoff\n\n## What Was Done\nBuilt the auth module.\n\n## Next Steps\nAdd tests.\n"
    )

    import nio.core.memory as mem_mod
    monkeypatch.setattr(mem_mod, "CLAUDE_HANDOFFS", handoffs_dir)

    from nio.core.memory import import_claude_handoffs
    count = import_claude_handoffs()
    assert count >= 2
