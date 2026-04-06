"""Tests for nio/core/memory.py -- eternal memory system."""

import sqlite3

import pytest


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary NIO database for testing."""
    db_path = tmp_path / "nio.db"
    monkeypatch.setenv("NIO_DB_PATH", str(db_path))

    # Patch get_connection to use tmp db
    import nio.core.db as db_mod
    def patched_get_connection():
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    monkeypatch.setattr(db_mod, "get_connection", patched_get_connection)

    # Init schema
    db_mod.init_db.__wrapped__() if hasattr(db_mod.init_db, '__wrapped__') else db_mod.init_db()

    return db_path


@pytest.fixture
def hermes_memories(tmp_path, monkeypatch):
    """Create fake Hermes memory files."""
    mem_dir = tmp_path / ".hermes" / "memories"
    mem_dir.mkdir(parents=True)

    (mem_dir / "MEMORY.md").write_text(
        "# Memory\n\n"
        "First paragraph about the project.\n\n"
        "Second paragraph about architecture.\n\n"
        "Short\n\n"  # Too short, should be skipped
        "Third paragraph about deployment strategy and scaling.\n"
    )

    (mem_dir / "USER.md").write_text(
        "# User\n\n"
        "User is a backend engineer with 5 years experience.\n\n"
        "Prefers minimal frameworks and plain SQL.\n"
    )

    import nio.core.memory as mem_mod
    monkeypatch.setattr(mem_mod, "HERMES_MEMORIES", mem_dir)
    return mem_dir


@pytest.fixture
def claude_handoffs(tmp_path, monkeypatch):
    """Create fake Claude handoff files."""
    handoffs_dir = tmp_path / ".claude" / "handoffs"
    handoffs_dir.mkdir(parents=True)

    (handoffs_dir / "2026-04-05_120000_test-session.md").write_text(
        "# Context Handoff\n\n"
        "## What Was Done\nBuilt the authentication module with JWT tokens.\n\n"
        "## Next Steps\nAdd rate limiting and token refresh.\n"
    )

    (handoffs_dir / "2026-04-05_130000_old-session_done.md").write_text(
        "# Already consumed handoff\nShould be skipped.\n"
    )

    import nio.core.memory as mem_mod
    monkeypatch.setattr(mem_mod, "CLAUDE_HANDOFFS", handoffs_dir)
    return handoffs_dir


def test_import_hermes_memories(tmp_db, hermes_memories):
    from nio.core.memory import import_hermes_memories

    count = import_hermes_memories()
    assert count >= 3  # 2 from MEMORY.md (short one skipped) + 2 from USER.md


def test_import_hermes_dedup(tmp_db, hermes_memories):
    from nio.core.memory import import_hermes_memories

    first = import_hermes_memories()
    second = import_hermes_memories()
    assert first > 0
    assert second == 0  # All already imported


def test_import_no_hermes(tmp_db, tmp_path, monkeypatch):
    import nio.core.memory as mem_mod
    monkeypatch.setattr(mem_mod, "HERMES_MEMORIES", tmp_path / "nonexistent")

    from nio.core.memory import import_hermes_memories
    count = import_hermes_memories()
    assert count == 0


def test_import_claude_handoffs(tmp_db, claude_handoffs):
    from nio.core.memory import import_claude_handoffs

    count = import_claude_handoffs()
    assert count >= 2  # Sections from the non-done file


def test_handoffs_skip_done_files(tmp_db, claude_handoffs):
    from nio.core.memory import import_claude_handoffs

    import_claude_handoffs()
    # Should not import from _done.md file
    import nio.core.db as db_mod
    conn = db_mod.get_connection()
    rows = conn.execute("SELECT content FROM memory_context WHERE source = 'claude_handoff'").fetchall()
    conn.close()
    for row in rows:
        assert "Already consumed" not in row[0]


def test_get_session_context(tmp_db):
    from nio.core.memory import get_session_context

    ctx = get_session_context()
    assert "session_count" in ctx
    assert "turn_count" in ctx
    assert "memory_facts" in ctx
    assert isinstance(ctx["memory_facts"], list)


def test_summarize_session_empty(tmp_db):
    from nio.core.memory import summarize_session

    result = summarize_session("nonexistent-session-id")
    assert result == ""


def test_summarize_session_with_data(tmp_db):
    import nio.core.db as db_mod
    conn = db_mod.get_connection()

    # Insert a session with turns
    conn.execute(
        "INSERT INTO sessions (session_id, started_at, ended_at, soul_id, task_type) "
        "VALUES ('test-sess-1', '2026-04-05T10:00:00', '2026-04-05T10:30:00', 'nio-core', 'coding')"
    )
    conn.execute(
        "INSERT INTO turns (turn_id, session_id, turn_index, user_msg, agent_msg, slop_score, created_at) "
        "VALUES ('t1', 'test-sess-1', 1, 'fix the auth bug', 'Updated the token validation.', 95.0, '2026-04-05T10:01:00')"
    )
    conn.execute(
        "INSERT INTO turns (turn_id, session_id, turn_index, user_msg, agent_msg, slop_score, created_at) "
        "VALUES ('t2', 'test-sess-1', 2, 'add tests', 'Added 5 test cases.', 98.0, '2026-04-05T10:10:00')"
    )
    conn.commit()
    conn.close()

    from nio.core.memory import summarize_session
    summary = summarize_session("test-sess-1")
    assert "coding" in summary
    assert "nio-core" in summary
    assert "2 turns" in summary
    assert "fix the auth" in summary


def test_sync_back_to_hermes(tmp_path, monkeypatch):
    import nio.core.memory as mem_mod
    hermes_dir = tmp_path / ".hermes" / "memories"
    hermes_dir.mkdir(parents=True)
    (hermes_dir / "MEMORY.md").write_text("# Existing memory\n\nSome facts.\n")

    monkeypatch.setattr(mem_mod, "HERMES_MEMORIES", hermes_dir)

    from nio.core.memory import sync_back_to_hermes
    sync_back_to_hermes({"session_count": 10, "turn_count": 50, "last_session_summary": "coding task"})

    content = (hermes_dir / "MEMORY.md").read_text()
    assert "NIO Context (auto-synced)" in content
    assert "Sessions: 10" in content
    assert "Turns: 50" in content


def test_sync_replaces_existing_section(tmp_path, monkeypatch):
    import nio.core.memory as mem_mod
    hermes_dir = tmp_path / ".hermes" / "memories"
    hermes_dir.mkdir(parents=True)
    (hermes_dir / "MEMORY.md").write_text(
        "# Memory\n\n## NIO Context (auto-synced)\nSessions: 5\n\n## Other Section\nKeep this.\n"
    )

    monkeypatch.setattr(mem_mod, "HERMES_MEMORIES", hermes_dir)

    from nio.core.memory import sync_back_to_hermes
    sync_back_to_hermes({"session_count": 20, "turn_count": 100, "last_session_summary": "updated"})

    content = (hermes_dir / "MEMORY.md").read_text()
    assert "Sessions: 20" in content
    assert "Sessions: 5" not in content
    assert "Other Section" in content
