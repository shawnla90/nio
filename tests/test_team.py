"""Tests for nio/core/team.py -- team mode operations."""

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary NIO database for testing."""
    db_path = tmp_path / "nio.db"

    import nio.core.db as db_mod
    def patched_get_connection():
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    monkeypatch.setattr(db_mod, "get_connection", patched_get_connection)
    db_mod.init_db()
    return db_path


def test_init_team_creates_structure(tmp_path, monkeypatch, tmp_db):
    """init_team creates .nio/ directory with team.toml and soul."""
    monkeypatch.chdir(tmp_path)

    from nio.core.team import init_team
    result = init_team("test-team", base_soul="nio-core", voice="shawn-builder")

    assert result["team_id"] == "test-team"
    assert (tmp_path / ".nio" / "team.toml").exists()
    assert (tmp_path / ".nio" / "souls").is_dir()
    assert (tmp_path / ".nio" / "memory").is_dir()


def test_init_team_config_content(tmp_path, monkeypatch, tmp_db):
    """team.toml contains correct team ID and soul reference."""
    monkeypatch.chdir(tmp_path)

    from nio.core.team import init_team
    init_team("my-team")

    import tomllib
    with open(tmp_path / ".nio" / "team.toml", "rb") as f:
        config = tomllib.load(f)

    assert config["team"]["id"] == "my-team"
    assert config["soul"]["id"] == "my-team-core"
    assert config["memory"]["mode"] == "git-backed"


def test_init_team_creates_memory_files(tmp_path, monkeypatch, tmp_db):
    """init_team creates default memory directory with starter files."""
    monkeypatch.chdir(tmp_path)

    from nio.core.team import init_team
    init_team("mem-team")

    mem_dir = tmp_path / ".nio" / "memory"
    assert (mem_dir / "MEMORY.md").exists()
    assert (mem_dir / "TEAM-FACTS.md").exists()
    assert (mem_dir / "RECENT-DECISIONS.md").exists()


def test_parse_toml_simple():
    """Fallback TOML parser handles basic structure."""
    from nio.core.team import _parse_toml_simple

    text = """
[team]
id = "test"
name = "Test Team"

[soul]
id = "test-soul"
pinned_version = "0.1.0"

[trust]
require_signature = false
pin_voice_profile = true
"""
    result = _parse_toml_simple(text)
    assert result["team"]["id"] == "test"
    assert result["soul"]["pinned_version"] == "0.1.0"
    assert result["trust"]["require_signature"] is False
    assert result["trust"]["pin_voice_profile"] is True


def test_parse_toml_simple_comments():
    """Fallback parser ignores comments and empty lines."""
    from nio.core.team import _parse_toml_simple

    text = "# Comment\n[section]\nkey = \"value\"\n# Another comment\n"
    result = _parse_toml_simple(text)
    assert result["section"]["key"] == "value"


def test_register_team(tmp_db):
    """_register_team writes to team_state table."""
    from nio.core.team import _register_team
    import nio.core.db as db_mod

    _register_team("reg-team", "https://github.com/test/repo", "soul-1", "0.1.0", {"team": {"id": "reg-team"}})

    conn = db_mod.get_connection()
    row = conn.execute("SELECT team_id, origin_url FROM team_state WHERE team_id = 'reg-team'").fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "reg-team"
    assert row[1] == "https://github.com/test/repo"


def test_get_members_no_team(tmp_path, monkeypatch):
    """get_members returns empty when not in a team repo."""
    monkeypatch.chdir(tmp_path)

    from nio.core.team import get_members
    assert get_members() == []


def test_release_team_soul_delegates(monkeypatch):
    """release_team_soul delegates to versioning.release_soul."""
    from nio.core.team import release_team_soul

    calls = []
    def mock_release(soul_id, bump="patch", message=""):
        calls.append((soul_id, bump, message))
        return f"{soul_id}@0.1.1"

    monkeypatch.setattr("nio.core.versioning.release_soul", mock_release)
    result = release_team_soul("team-soul", bump="minor", message="test")
    assert len(calls) == 1
    assert calls[0] == ("team-soul", "minor", "test")
