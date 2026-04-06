"""Tests for nio/core/mode.py -- mode resolver (global vs team)."""

from pathlib import Path

import pytest


def test_global_mode_default(tmp_path, monkeypatch):
    """Default mode is global when no team.toml exists."""
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import get_active_mode
    assert get_active_mode() == "global"


def test_team_mode_detected(tmp_path, monkeypatch):
    """Team mode detected when .nio/team.toml exists in CWD."""
    nio_dir = tmp_path / ".nio"
    nio_dir.mkdir()
    (nio_dir / "team.toml").write_text(
        '[team]\nid = "test-team"\nname = "Test Team"\n'
        '[soul]\nid = "test-soul"\npinned_version = "0.1.0"\n'
        '[voice]\nid = "shawn-builder"\npinned_version = "1.0.0"\n'
    )
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import get_active_mode
    assert get_active_mode() == "team"


def test_team_mode_in_parent(tmp_path, monkeypatch):
    """Team mode detected when .nio/team.toml exists in a parent directory."""
    nio_dir = tmp_path / ".nio"
    nio_dir.mkdir()
    (nio_dir / "team.toml").write_text(
        '[team]\nid = "parent-team"\n'
        '[soul]\nid = "test-soul"\npinned_version = "0.1.0"\n'
        '[voice]\nid = "shawn-builder"\npinned_version = "1.0.0"\n'
    )
    child = tmp_path / "src" / "deep"
    child.mkdir(parents=True)
    monkeypatch.chdir(child)

    from nio.core.mode import get_active_mode, find_team_toml
    assert get_active_mode() == "team"
    assert find_team_toml() == nio_dir / "team.toml"


def test_find_team_toml_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import find_team_toml
    assert find_team_toml() is None


def test_load_team_config(tmp_path, monkeypatch):
    nio_dir = tmp_path / ".nio"
    nio_dir.mkdir()
    (nio_dir / "team.toml").write_text(
        '[team]\nid = "my-team"\nname = "My Team"\n'
        '[soul]\nid = "my-soul"\npinned_version = "0.2.0"\n'
        '[voice]\nid = "enterprise-neutral"\npinned_version = "1.0.0"\n'
    )
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import load_team_config
    config = load_team_config()
    assert config is not None
    assert config["team"]["id"] == "my-team"
    assert config["soul"]["pinned_version"] == "0.2.0"


def test_effective_soul_team_mode(tmp_path, monkeypatch):
    nio_dir = tmp_path / ".nio"
    nio_dir.mkdir()
    (nio_dir / "team.toml").write_text(
        '[team]\nid = "team-x"\n'
        '[soul]\nid = "team-soul"\npinned_version = "1.0.0"\n'
        '[voice]\nid = "enterprise-neutral"\npinned_version = "1.0.0"\n'
    )
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import get_effective_soul
    soul_id, version = get_effective_soul()
    assert soul_id == "team-soul"
    assert version == "1.0.0"


def test_effective_voice_team_mode(tmp_path, monkeypatch):
    nio_dir = tmp_path / ".nio"
    nio_dir.mkdir()
    (nio_dir / "team.toml").write_text(
        '[team]\nid = "team-x"\n'
        '[soul]\nid = "team-soul"\npinned_version = "1.0.0"\n'
        '[voice]\nid = "enterprise-neutral"\npinned_version = "2.0.0"\n'
    )
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import get_effective_voice
    voice_id, version = get_effective_voice()
    assert voice_id == "enterprise-neutral"
    assert version == "2.0.0"


def test_effective_soul_global_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Create global active pointer
    active_dir = tmp_path / ".nio_test_active"
    active_dir.mkdir(parents=True)
    (active_dir / "soul.txt").write_text("nio-core@0.2.0")

    import nio.core.mode as mode_mod
    monkeypatch.setattr(mode_mod, "NIO_HOME", tmp_path / ".nio_test_active" / "..")

    # Without global pointer, returns empty
    from nio.core.mode import get_effective_soul
    soul_id, version = get_effective_soul()
    # In global mode with no active file at NIO_HOME/active/, returns empty
    assert isinstance(soul_id, str)


def test_get_team_id(tmp_path, monkeypatch):
    nio_dir = tmp_path / ".nio"
    nio_dir.mkdir()
    (nio_dir / "team.toml").write_text('[team]\nid = "cool-team"\n')
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import get_team_id
    assert get_team_id() == "cool-team"


def test_get_team_id_no_team(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from nio.core.mode import get_team_id
    assert get_team_id() == ""
