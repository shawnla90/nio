"""Tests for CLI commands: metrics, team, status, doctor, install, cc."""

import sqlite3
from pathlib import Path

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


# Metrics commands

def test_metrics_show(runner, tmp_db):
    from nio.cli.cmd_metrics import app
    result = runner.invoke(app, ["show"])
    assert result.exit_code == 0


# Team commands

def test_team_init(runner, tmp_path, monkeypatch, tmp_db):
    monkeypatch.chdir(tmp_path)
    from nio.cli.cmd_team import app
    result = runner.invoke(app, ["init", "--name", "cli-test-team"])
    assert result.exit_code == 0
    assert (tmp_path / ".nio" / "team.toml").exists()


# CC commands

def test_cc_status_no_sessions(runner, tmp_db):
    from nio.cli.cmd_cc import app
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "no" in result.stdout.lower() or "start" in result.stdout.lower()


def test_cc_start(runner, tmp_db):
    from nio.cli.cmd_cc import app
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    assert "started" in result.stdout.lower()


def test_cc_start_then_status(runner, tmp_db):
    from nio.cli.cmd_cc import app
    runner.invoke(app, ["start"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "active" in result.stdout.lower()


def test_cc_turn_no_session(runner, tmp_db):
    from nio.cli.cmd_cc import app
    result = runner.invoke(app, ["turn", "--user", "test", "--agent", "response"])
    assert result.exit_code != 0 or "no active" in result.stdout.lower()


def test_cc_full_lifecycle(runner, tmp_db):
    from nio.cli.cmd_cc import app

    # Start
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0

    # Record turn
    result = runner.invoke(app, ["turn", "--user", "fix bug", "--agent", "Fixed the auth issue."])
    assert result.exit_code == 0
    assert "/100" in result.stdout

    # End
    result = runner.invoke(app, ["end"])
    assert result.exit_code == 0
    assert "ended" in result.stdout.lower()


def test_cc_context(runner, tmp_db):
    from nio.cli.cmd_cc import app
    result = runner.invoke(app, ["context"])
    assert result.exit_code == 0
    assert "mode" in result.stdout.lower() or "Mode" in result.stdout
