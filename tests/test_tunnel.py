"""Tests for nio.core.tunnel module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_check_cloudflared_installed_found(monkeypatch):
    from nio.core import tunnel
    monkeypatch.setattr("shutil.which", lambda x: "/opt/homebrew/bin/cloudflared")
    assert tunnel.check_cloudflared_installed() == "/opt/homebrew/bin/cloudflared"


def test_check_cloudflared_installed_missing(monkeypatch):
    from nio.core import tunnel
    monkeypatch.setattr("shutil.which", lambda x: None)
    assert tunnel.check_cloudflared_installed() is None


def test_get_access_config_default(tmp_path, monkeypatch):
    from nio.core import tunnel
    monkeypatch.setattr(tunnel, "CONFIG_PATH", tmp_path / "config.yaml")
    assert tunnel.get_access_config() == {"mode": "local"}


def test_get_access_config_reads(tmp_path, monkeypatch):
    from nio.core import tunnel
    config_path = tmp_path / "config.yaml"
    config_path.write_text("access:\n  mode: remote\n  tunnel_name: nio-chat\n  tunnel_url: nio.shawnos.ai\n")
    monkeypatch.setattr(tunnel, "CONFIG_PATH", config_path)
    result = tunnel.get_access_config()
    assert result["mode"] == "remote"
    assert result["tunnel_name"] == "nio-chat"
    assert result["tunnel_url"] == "nio.shawnos.ai"


def test_write_access_config_creates(tmp_path, monkeypatch):
    from nio.core import tunnel
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(tunnel, "CONFIG_PATH", config_path)
    tunnel.write_access_config(mode="remote", tunnel_name="test", tunnel_url="test.example.com")
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)
    assert config["access"]["mode"] == "remote"
    assert config["access"]["tunnel_name"] == "test"
    assert config["access"]["tunnel_url"] == "test.example.com"


def test_write_access_config_preserves_existing(tmp_path, monkeypatch):
    from nio.core import tunnel
    config_path = tmp_path / "config.yaml"
    config_path.write_text("mode: global\ndash:\n  port: 4242\n")
    monkeypatch.setattr(tunnel, "CONFIG_PATH", config_path)
    tunnel.write_access_config(mode="local")
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)
    assert config["mode"] == "global"
    assert config["dash"]["port"] == 4242
    assert config["access"]["mode"] == "local"


def test_is_tunnel_running_true(monkeypatch):
    from nio.core import tunnel
    mock_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr(subprocess, "run", mock_run)
    assert tunnel.is_tunnel_running() is True


def test_is_tunnel_running_false(monkeypatch):
    from nio.core import tunnel
    mock_run = MagicMock(return_value=MagicMock(returncode=1))
    monkeypatch.setattr(subprocess, "run", mock_run)
    assert tunnel.is_tunnel_running() is False


def test_check_logged_in_false(monkeypatch):
    from nio.core import tunnel
    mock_run = MagicMock(return_value=MagicMock(returncode=1))
    monkeypatch.setattr(subprocess, "run", mock_run)
    assert tunnel.check_cloudflared_logged_in() is False
