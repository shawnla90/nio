"""Team mode: init, join, sync, members, release."""

from __future__ import annotations

import json
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
    import shutil
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
    """Join a team by pulling its .nio/team.toml."""
    # Stub: in full implementation, this clones the repo, verifies signature,
    # installs team soul under ~/.nio/teams/{team_id}/
    return {
        "team_id": "unknown",
        "soul_id": "unknown",
        "soul_version": "0.1.0",
    }


def sync_team() -> dict:
    """Pull latest team state from the repo."""
    # Stub: git pull .nio/ directory, verify signatures, update local cache
    return {"team_id": "unknown", "soul_version": "0.1.0"}


def get_members() -> list[dict]:
    """List team members and their soul versions."""
    # Stub: read from team_state in nio.db
    return []


def release_team_soul(soul_id: str, bump: str = "patch", message: str = "") -> str:
    """Release a new team soul version (owner-only)."""
    from nio.core.versioning import release_soul
    return release_soul(soul_id, bump=bump, message=message)
