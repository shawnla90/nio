"""Mode resolver: global vs team.

Determines which soul/voice to use based on CWD and config.
- Team mode: if CWD (or any parent) contains .nio/team.toml
- Global mode: uses ~/.nio/active/soul.txt and voice.txt
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

NIO_HOME = Path.home() / ".nio"


def get_active_mode() -> str:
    """Return 'team' if CWD has .nio/team.toml, else 'global'."""
    team_toml = find_team_toml()
    if team_toml:
        return "team"
    return "global"


def find_team_toml() -> Optional[Path]:
    """Walk up from CWD looking for .nio/team.toml."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".nio" / "team.toml"
        if candidate.exists():
            return candidate
        # Stop at home directory
        if parent == Path.home():
            break
    return None


def load_team_config() -> Optional[dict]:
    """Load and parse .nio/team.toml if present."""
    toml_path = find_team_toml()
    if not toml_path:
        return None
    try:
        # Use tomllib (3.11+) or fallback to simple parsing
        try:
            import tomllib
            with open(toml_path, "rb") as f:
                return tomllib.load(f)
        except ImportError:
            import tomli
            with open(toml_path, "rb") as f:
                return tomli.load(f)
    except Exception:
        return None


def get_effective_soul() -> tuple[str, str]:
    """Return (soul_id, soul_version) based on active mode.

    Team mode: from .nio/team.toml [soul] section.
    Global mode: from ~/.nio/active/soul.txt.
    """
    mode = get_active_mode()

    if mode == "team":
        config = load_team_config()
        if config and "soul" in config:
            soul_id = config["soul"].get("id", "")
            soul_version = config["soul"].get("pinned_version", "0.1.0")
            return soul_id, soul_version

    # Global mode
    active_file = NIO_HOME / "active" / "soul.txt"
    if active_file.exists():
        ref = active_file.read_text().strip()
        if "@" in ref:
            soul_id, version = ref.split("@", 1)
            return soul_id, version
        return ref, "0.1.0"

    return "", ""


def get_effective_voice() -> tuple[str, str]:
    """Return (voice_id, voice_version) based on active mode."""
    mode = get_active_mode()

    if mode == "team":
        config = load_team_config()
        if config and "voice" in config:
            voice_id = config["voice"].get("id", "")
            voice_version = config["voice"].get("pinned_version", "1.0.0")
            return voice_id, voice_version

    # Global mode
    active_file = NIO_HOME / "active" / "voice.txt"
    if active_file.exists():
        ref = active_file.read_text().strip()
        if "@" in ref:
            voice_id, version = ref.split("@", 1)
            return voice_id, version
        return ref, "1.0.0"

    return "", ""


def get_team_id() -> str:
    """Return the team ID if in team mode, else empty string."""
    config = load_team_config()
    if config and "team" in config:
        return config["team"].get("id", "")
    return ""
