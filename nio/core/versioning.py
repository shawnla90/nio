"""Soul and voice versioning: release, diff, checkout, rollback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import frontmatter


def bump_semver(version: str, bump: str = "patch") -> str:
    """Bump a semver string. Returns new version."""
    parts = version.split(".")
    if len(parts) != 3:
        parts = ["0", "1", "0"]
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump == "major":
        return f"{major + 1}.0.0"
    elif bump == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


def release_soul(soul_id: str, bump: str = "patch", message: str = "") -> str:
    """Release a new soul version: bump frontmatter, snapshot to DB, commit to git."""
    from nio.core.soul import get_soul_path, load_soul, body_sha256
    from nio.core.db import get_connection

    path = get_soul_path(soul_id)
    if not path or not path.exists():
        raise FileNotFoundError(f"Soul not found: {soul_id}")

    post = frontmatter.load(path)
    old_version = post.metadata.get("version", "0.0.0")
    new_version = bump_semver(old_version, bump)

    # Update frontmatter
    post.metadata["version"] = new_version
    changelog = post.metadata.get("changelog", [])
    changelog.insert(0, f'{new_version}: "{message}"')
    post.metadata["changelog"] = changelog

    # Write updated file
    path.write_text(frontmatter.dumps(post))

    # Snapshot to DB
    body = post.content
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO soul_versions
           (soul_id, version, body_sha256, body, frontmatter, released_at, released_by, changelog)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            soul_id, new_version, body_sha256(body), body,
            json.dumps(dict(post.metadata)), datetime.now(timezone.utc).isoformat(),
            "local", message,
        ),
    )
    conn.commit()
    conn.close()

    # Git commit if in a git repo
    _git_commit(path, f"nio: release {soul_id}@{new_version} - {message}")

    return new_version


def release_voice(voice_id: str, bump: str = "patch", message: str = "") -> str:
    """Release a new voice profile version."""
    from nio.core.voice import _find_voice
    from nio.core.db import get_connection

    path = _find_voice(voice_id)
    if not path or not path.exists():
        raise FileNotFoundError(f"Voice not found: {voice_id}")

    post = frontmatter.load(path)
    old_version = post.metadata.get("version", "0.0.0")
    new_version = bump_semver(old_version, bump)

    post.metadata["version"] = new_version
    path.write_text(frontmatter.dumps(post))

    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO voice_versions
           (voice_id, version, body, rules, released_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            voice_id, new_version, post.content,
            json.dumps(dict(post.metadata)), datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    _git_commit(path, f"nio: release {voice_id}@{new_version} - {message}")
    return new_version


def diff_souls(ref_a: str, ref_b: str):
    """Print a diff between two soul versions with metric deltas."""
    from nio.core.soul import load_soul
    from rich.console import Console
    from rich.table import Table
    import difflib

    console = Console()
    a = load_soul(ref_a)
    b = load_soul(ref_b)

    if not a or not b:
        console.print(f"[red]Could not load one or both refs: {ref_a}, {ref_b}[/red]")
        return

    # Prompt diff
    diff = difflib.unified_diff(
        a["body"].splitlines(keepends=True),
        b["body"].splitlines(keepends=True),
        fromfile=ref_a,
        tofile=ref_b,
    )
    diff_text = "".join(diff)
    if diff_text:
        console.print(f"\n[bold]Prompt diff:[/bold]")
        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                console.print(f"[green]{line}[/green]")
            elif line.startswith("-") and not line.startswith("---"):
                console.print(f"[red]{line}[/red]")
            else:
                console.print(f"[dim]{line}[/dim]")
    else:
        console.print("[dim]No prompt body changes.[/dim]")

    # Frontmatter diff
    console.print(f"\n[bold]Frontmatter changes:[/bold]")
    a_meta = a.get("metadata", {})
    b_meta = b.get("metadata", {})
    all_keys = sorted(set(list(a_meta.keys()) + list(b_meta.keys())))
    for key in all_keys:
        va = a_meta.get(key)
        vb = b_meta.get(key)
        if va != vb:
            console.print(f"  [red]- {key}: {va}[/red]")
            console.print(f"  [green]+ {key}: {vb}[/green]")

    # Metric deltas (from DB turns if available)
    _print_metric_deltas(console, ref_a, ref_b)


def diff_voices(ref_a: str, ref_b: str):
    """Print a diff between two voice profile versions."""
    from nio.core.voice import load_voice
    from rich.console import Console
    import difflib

    console = Console()
    a = load_voice(ref_a)
    b = load_voice(ref_b)

    if not a or not b:
        console.print(f"[red]Could not load one or both refs: {ref_a}, {ref_b}[/red]")
        return

    diff = difflib.unified_diff(
        a["body"].splitlines(keepends=True),
        b["body"].splitlines(keepends=True),
        fromfile=ref_a,
        tofile=ref_b,
    )
    for line in "".join(diff).splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            console.print(f"[green]{line}[/green]")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"[red]{line}[/red]")
        else:
            console.print(f"[dim]{line}[/dim]")


def checkout_soul(soul_ref: str):
    """Restore a soul version from the DB snapshot."""
    from nio.core.soul import get_soul_path, _load_from_db, LOCAL_REGISTRY

    if "@" not in soul_ref:
        raise ValueError("Checkout requires soul_id@version format")

    soul_id, version = soul_ref.split("@", 1)
    snapshot = _load_from_db(soul_id, version)
    if not snapshot:
        raise FileNotFoundError(f"No snapshot found: {soul_ref}")

    # Reconstruct the file
    meta = snapshot["metadata"]
    body = snapshot["body"]
    import frontmatter as fm
    post = fm.Post(body, **meta)

    target = LOCAL_REGISTRY / f"{soul_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fm.dumps(post))

    # Update active pointer
    from nio.core.soul import set_active_soul
    set_active_soul(soul_id)


def _print_metric_deltas(console, ref_a: str, ref_b: str):
    """Print metric deltas between two soul versions from the turns table."""
    from nio.core.db import get_connection
    from rich.table import Table

    def _parse_ref(ref: str):
        if "@" in ref:
            return ref.split("@", 1)
        return ref, None

    soul_a, ver_a = _parse_ref(ref_a)
    soul_b, ver_b = _parse_ref(ref_b)

    conn = get_connection()

    def _get_stats(soul_id, version):
        rows = conn.execute(
            """SELECT AVG(t.slop_score), AVG(t.latency_ms), AVG(t.user_signal), COUNT(t.turn_id)
               FROM turns t JOIN sessions s ON t.session_id = s.session_id
               WHERE s.soul_id = ? AND s.soul_version = ?""",
            (soul_id, version or ""),
        ).fetchone()
        return {
            "slop_avg": rows[0] or 0, "latency_avg": rows[1] or 0,
            "signal_avg": rows[2] or 0, "turn_count": rows[3] or 0,
        }

    stats_a = _get_stats(soul_a, ver_a)
    stats_b = _get_stats(soul_b, ver_b)
    conn.close()

    if stats_a["turn_count"] == 0 and stats_b["turn_count"] == 0:
        console.print("\n[dim]No session data for either version.[/dim]")
        return

    table = Table(title="Metric Deltas")
    table.add_column("Metric", style="bold")
    table.add_column(ref_a)
    table.add_column(ref_b)
    table.add_column("Delta")

    for label, key, fmt in [
        ("Slop avg", "slop_avg", ".1f"),
        ("Latency avg (ms)", "latency_avg", ".0f"),
        ("User signal", "signal_avg", "+.2f"),
        ("Turn count", "turn_count", "d"),
    ]:
        va = stats_a[key]
        vb = stats_b[key]
        delta = vb - va
        delta_str = f"{delta:{fmt}}" if isinstance(delta, (int, float)) else str(delta)
        table.add_row(label, f"{va:{fmt}}", f"{vb:{fmt}}", delta_str)

    console.print(table)


def _git_commit(path: Path, message: str):
    """Attempt a git commit if the file is in a repo. Fail silently."""
    import subprocess

    try:
        subprocess.run(
            ["git", "add", str(path)],
            cwd=path.parent, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=path.parent, capture_output=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
