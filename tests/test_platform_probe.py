"""Tests for nio/core/platform_probe.py -- platform detection."""

from pathlib import Path

import pytest


@pytest.fixture
def hermes_env(tmp_path, monkeypatch):
    """Create a fake .hermes directory with .env file."""
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    env_file = hermes_dir / ".env"
    env_file.write_text("DISCORD_BOT_TOKEN=test_token_123\nTELEGRAM_BOT_TOKEN=\n")

    import nio.core.platform_probe as probe_mod
    monkeypatch.setattr(probe_mod, "HERMES_HOME", hermes_dir)
    monkeypatch.setattr(probe_mod, "HERMES_ENV", env_file)
    return hermes_dir


def test_platforms_defined():
    from nio.core.platform_probe import PLATFORMS
    assert len(PLATFORMS) == 5
    assert "discord" in PLATFORMS
    assert "telegram" in PLATFORMS
    assert "whatsapp" in PLATFORMS
    assert "slack" in PLATFORMS
    assert "signal" in PLATFORMS


def test_probe_configured_platform(hermes_env):
    from nio.core.platform_probe import probe_platform
    result = probe_platform("discord")
    assert result["configured"] is True
    assert "test_" in result["token_preview"]


def test_probe_unconfigured_platform(hermes_env):
    from nio.core.platform_probe import probe_platform
    result = probe_platform("telegram")
    assert result["configured"] is False


def test_probe_all(hermes_env):
    from nio.core.platform_probe import probe_all
    results = probe_all()
    assert len(results) == 5
    platforms = {r["platform"] for r in results}
    assert platforms == {"discord", "telegram", "whatsapp", "slack", "signal"}


def test_configure_platform(hermes_env):
    from nio.core.platform_probe import configure_platform, probe_platform

    configure_platform("slack", "xoxb-new-token")
    result = probe_platform("slack")
    assert result["configured"] is True


def test_read_env(hermes_env):
    from nio.core.platform_probe import _read_env
    env = _read_env()
    assert env["DISCORD_BOT_TOKEN"] == "test_token_123"


def test_write_env_preserves_existing(hermes_env):
    from nio.core.platform_probe import _write_env, _read_env

    _write_env("NEW_KEY", "new_value")
    env = _read_env()
    assert env["DISCORD_BOT_TOKEN"] == "test_token_123"
    assert env["NEW_KEY"] == "new_value"


def test_probe_nonexistent_platform(hermes_env):
    from nio.core.platform_probe import probe_platform
    result = probe_platform("nonexistent")
    assert result["configured"] is False
