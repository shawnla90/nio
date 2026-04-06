"""Team mode: init, join, sync, members, release."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


def init_team(
    name: str,
    base_soul: str = "nio-core",
    voice: str = "shawn-builder",
) -> dict:
    """Initialize team mode in the current directory."""
    cwd = Path.cwd()
    nio_dir = cwd / ".nio"
    nio_dir.mkdir(exist_ok=True)
    (nio_dir / "souls").mkdir(exist_ok=True)
    (nio_dir / "memory").mkdir(exist_ok=True)

    # Create team soul derived from base
    soul_id = f"{name}-core"
    from nio.core.soul import create_soul
    soul_path = create_soul(soul_id, from_soul=base_soul, voice=voice)

    # Move soul into team dir
    team_soul = nio_dir / "souls" / f"{soul_id}.md"
    shutil.move(str(soul_path), str(team_soul))

    # Write team.toml
    config_path = nio_dir / "team.toml"
    config_path.write_text(f"""[team]
id = "{name}"
name = "{name.replace('-', ' ').title()}"
origin = ""
created_at = "{datetime.utcnow().isoformat()}Z"

[soul]
id = "{soul_id}"
pinned_version = "0.1.0"
source = ".nio/souls/{soul_id}.md"

[voice]
id = "{voice}"
pinned_version = "1.0.0"

[memory]
mode = "git-backed"
location = ".nio/memory/"
sync_policy = "pull-on-start"

[permissions]
owners = []
releasers = []
members = ["*"]
soul_release_mode = "owner"

[trust]
require_signature = false
signing_key_fingerprint = ""
pin_voice_profile = true
""")

    # Init memory files
    (nio_dir / "memory" / "MEMORY.md").write_text("# Team Memory\n")
    (nio_dir / "memory" / "TEAM-FACTS.md").write_text("# Team Facts\n")
    (nio_dir / "memory" / "RECENT-DECISIONS.md").write_text("# Recent Decisions\n")

    return {
        "team_id": name,
        "config_path": str(config_path),
        "soul_path": str(team_soul),
        "origin": "",
    }


def join_team(repo_url: str) -> dict:
    """Join a team by cloning its .nio/ directory.

    1. Sparse-clone the repo's .nio/ directory to a temp location
    2. Read .nio/team.toml to extract team_id
    3. Copy .nio/ to ~/.nio/teams/{team_id}/
    4. Register in team_state table
    """
    import tempfile

    NIO_HOME = Path.home() / ".nio"
    tmp = Path(tempfile.mkdtemp(prefix="nio-join-"))

    try:
        # Sparse clone just .nio/
        subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", repo_url, str(tmp / "repo")],
            capture_output=True, check=True, timeout=30,
        )
        subprocess.run(
            ["git", "sparse-checkout", "set", ".nio"],
            cwd=str(tmp / "repo"), capture_output=True, check=True,
        )

        team_toml = tmp / "repo" / ".nio" / "team.toml"
        if not team_toml.exists():
            raise FileNotFoundError("No .nio/team.toml found in repo")

        # Parse team config
        import tomllib
        with open(team_toml, "rb") as f:
            config = tomllib.load(f)

        team_id = config.get("team", {}).get("id", "unknown")
        soul_id = config.get("soul", {}).get("id", "")
        soul_version = config.get("soul", {}).get("pinned_version", "0.1.0")

        # Copy .nio/ to ~/.nio/teams/{team_id}/
        teams_dir = NIO_HOME / "teams" / team_id
        if teams_dir.exists():
            shutil.rmtree(teams_dir)
        shutil.copytree(tmp / "repo" / ".nio", teams_dir)

        # Register in team_state table
        _register_team(team_id, repo_url, soul_id, soul_version, config)

        return {
            "team_id": team_id,
            "soul_id": soul_id,
            "soul_version": soul_version,
            "installed_to": str(teams_dir),
        }

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sync_team() -> dict:
    """Pull latest team state from the origin repo.

    Reads .nio/team.toml for origin URL, fetches updates,
    compares soul version, updates local registry.
    """
    from nio.core.mode import find_team_toml, load_team_config

    toml_path = find_team_toml()
    if not toml_path:
        return {"error": "No .nio/team.toml found in current directory tree"}

    config = load_team_config()
    if not config:
        return {"error": "Could not parse .nio/team.toml"}

    team_id = config.get("team", {}).get("id", "unknown")
    origin = config.get("team", {}).get("origin", "")

    if not origin:
        return {"team_id": team_id, "synced": False, "reason": "No origin URL configured"}

    # Git pull the .nio/ directory
    nio_dir = toml_path.parent
    repo_root = nio_dir.parent

    try:
        result = subprocess.run(
            ["git", "pull", "--rebase", "origin"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=30,
        )

        # Re-read config after pull
        config = load_team_config()
        soul_id = config.get("soul", {}).get("id", "") if config else ""
        soul_version = config.get("soul", {}).get("pinned_version", "") if config else ""

        # Update team_state in DB
        _register_team(team_id, origin, soul_id, soul_version, config or {})

        return {
            "team_id": team_id,
            "synced": True,
            "soul_id": soul_id,
            "soul_version": soul_version,
            "git_output": result.stdout.strip(),
        }

    except subprocess.TimeoutExpired:
        return {"team_id": team_id, "synced": False, "reason": "Git pull timed out"}
    except subprocess.CalledProcessError as e:
        return {"team_id": team_id, "synced": False, "reason": e.stderr.strip()}


def get_members() -> list[dict]:
    """List team members from git log of .nio/ directory."""
    from nio.core.mode import find_team_toml

    toml_path = find_team_toml()
    if not toml_path:
        return []

    repo_root = toml_path.parent.parent
    try:
        result = subprocess.run(
            ["git", "log", "--format=%an <%ae>", "--", ".nio/"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
        authors = list(dict.fromkeys(result.stdout.strip().splitlines()))
        return [{"name": a.split(" <")[0], "email": a} for a in authors[:20]]
    except Exception:
        return []


def release_team_soul(soul_id: str, bump: str = "patch", message: str = "") -> str:
    """Release a new team soul version (owner-only)."""
    from nio.core.versioning import release_soul
    return release_soul(soul_id, bump=bump, message=message)


def _register_team(team_id: str, origin: str, soul_id: str, soul_version: str, config: dict):
    """Write team info to the team_state table."""
    try:
        from nio.core.db import get_connection
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO team_state
               (team_id, origin_url, soul_id, soul_version, manifest, last_sync_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (team_id, origin, soul_id, soul_version,
             json.dumps(config), datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB might not be initialized yet


def _parse_toml_simple(text: str) -> dict:
    """Minimal TOML parser for team.toml (fallback when tomllib unavailable)."""
    result: dict = {}
    current_section = result
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            parts = section.split(".")
            current_section = result
            for part in parts:
                current_section = current_section.setdefault(part, {})
        elif "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            current_section[key] = value
    return result
