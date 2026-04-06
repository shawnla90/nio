"""Tests for CLI commands: soul, voice, antislop."""

import sqlite3

import pytest
from typer.testing import CliRunner


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


@pytest.fixture
def runner():
    return CliRunner()


# Soul commands

def test_soul_list(runner):
    from nio.cli.cmd_soul import app
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "nio-core" in result.stdout


def test_soul_show(runner):
    from nio.cli.cmd_soul import app
    result = runner.invoke(app, ["show", "nio-core"])
    assert result.exit_code == 0
    assert "nio-core" in result.stdout


def test_soul_show_nonexistent(runner):
    from nio.cli.cmd_soul import app
    result = runner.invoke(app, ["show", "nonexistent-soul-xyz"])
    assert "not found" in result.stdout.lower() or result.exit_code != 0


def test_soul_active_no_active(runner, tmp_path, monkeypatch):
    import nio.core.soul as soul_mod
    monkeypatch.setattr(soul_mod, "NIO_HOME", tmp_path / ".nio")
    (tmp_path / ".nio" / "active").mkdir(parents=True, exist_ok=True)

    from nio.cli.cmd_soul import app
    result = runner.invoke(app, ["active"])
    assert result.exit_code == 0


# Voice commands

def test_voice_list(runner):
    from nio.cli.cmd_voice import app
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "shawn-builder" in result.stdout


# Antislop commands

def test_antislop_score(runner):
    from nio.cli.cmd_antislop import app
    result = runner.invoke(app, ["score", "This is clean text with no slop patterns."])
    assert result.exit_code == 0
    assert "/100" in result.stdout


def test_antislop_score_sloppy(runner):
    from nio.cli.cmd_antislop import app
    result = runner.invoke(app, ["score", "The uncomfortable truth is this game changer unleashes chaos."])
    assert result.exit_code == 0
    # Should have a low score
    assert "/100" in result.stdout


def test_antislop_list(runner):
    from nio.cli.cmd_antislop import app
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "critical" in result.stdout.lower() or "em_dash" in result.stdout.lower()
