"""Soul loader, schema, and inheritance resolver."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import frontmatter

NIO_HOME = Path.home() / ".nio"
REGISTRY_DIR = Path(__file__).parent.parent.parent / "registry" / "souls"
LOCAL_REGISTRY = NIO_HOME / "registry" / "souls"


def get_soul_path(soul_id: str) -> Optional[Path]:
    """Find a soul file by ID, checking local registry then bundled."""
    local = LOCAL_REGISTRY / f"{soul_id}.md"
    if local.exists():
        return local
    bundled = REGISTRY_DIR / f"{soul_id}.md"
    if bundled.exists():
        return bundled
    return None


def load_soul(soul_ref: str) -> Optional[dict]:
    """Load a soul by reference (id or id@version).

    Returns dict with keys: metadata (frontmatter), body (prompt), raw (full file).
    For versioned refs, loads from the DB snapshot.
    """
    if "@" in soul_ref:
        soul_id, version = soul_ref.split("@", 1)
        return _load_from_db(soul_id, version)

    path = get_soul_path(soul_ref)
    if not path or not path.exists():
        return None

    post = frontmatter.load(path)
    return {
        "metadata": dict(post.metadata),
        "body": post.content,
        "raw": path.read_text(),
        "soul": post.metadata.get("soul", soul_ref),
        "version": post.metadata.get("version", "0.0.0"),
        "voice": post.metadata.get("voice", ""),
        "description": post.metadata.get("description", ""),
    }


def _load_from_db(soul_id: str, version: str) -> Optional[dict]:
    """Load a soul snapshot from the database."""
    from nio.core.db import get_connection

    conn = get_connection()
    row = conn.execute(
        "SELECT body, frontmatter FROM soul_versions WHERE soul_id = ? AND version = ?",
        (soul_id, version),
    ).fetchone()
    conn.close()

    if not row:
        return None

    import json
    meta = json.loads(row[1])
    return {
        "metadata": meta,
        "body": row[0],
        "raw": row[0],
        "soul": soul_id,
        "version": version,
        "voice": meta.get("voice", ""),
        "description": meta.get("description", ""),
    }


def list_souls() -> list[dict]:
    """List all available souls from the local registry."""
    souls = []
    for registry in [LOCAL_REGISTRY, REGISTRY_DIR]:
        if not registry.exists():
            continue
        for path in sorted(registry.glob("*.md")):
            try:
                post = frontmatter.load(path)
                souls.append({
                    "soul": post.metadata.get("soul", path.stem),
                    "version": post.metadata.get("version", "0.0.0"),
                    "voice": post.metadata.get("voice", ""),
                    "description": post.metadata.get("description", ""),
                    "path": str(path),
                })
            except Exception:
                continue
    # Deduplicate by soul ID, prefer local
    seen = set()
    unique = []
    for s in souls:
        if s["soul"] not in seen:
            seen.add(s["soul"])
            unique.append(s)
    return unique


def get_active_soul() -> Optional[str]:
    """Return the active soul reference (e.g., 'nio-core@0.1.0')."""
    active_file = NIO_HOME / "active" / "soul.txt"
    if active_file.exists():
        return active_file.read_text().strip()
    return None


def set_active_soul(soul_id: str):
    """Set the active soul."""
    active_file = NIO_HOME / "active" / "soul.txt"
    active_file.parent.mkdir(parents=True, exist_ok=True)

    soul = load_soul(soul_id)
    if soul:
        ref = f"{soul['soul']}@{soul['version']}"
    else:
        ref = soul_id
    active_file.write_text(ref)


def resolve_soul_with_inheritance(soul_id: str) -> dict:
    """Resolve a soul's full prompt by walking the derived_from chain.

    Merges: base voice -> base antislop overrides -> base targets -> base body -> child overrides.
    Child body is appended unless prompt_mode: replace.
    Detects cycles.
    """
    chain = []
    visited = set()
    current_id = soul_id

    while current_id:
        if current_id in visited:
            raise ValueError(f"Circular inheritance detected: {' -> '.join(chain)} -> {current_id}")
        visited.add(current_id)
        chain.append(current_id)

        soul = load_soul(current_id)
        if not soul:
            break

        derived = soul["metadata"].get("derived_from")
        if derived:
            # Strip version for lookup
            current_id = derived.split("@")[0] if "@" in derived else derived
        else:
            current_id = None

    # Reverse so base is first
    chain.reverse()

    # Merge
    merged = {"metadata": {}, "body": "", "voice": "", "antislop": {}, "targets": {}}
    for sid in chain:
        soul = load_soul(sid)
        if not soul:
            continue
        meta = soul["metadata"]
        merged["voice"] = meta.get("voice", merged["voice"])
        merged["antislop"].update(meta.get("antislop", {}))
        merged["targets"].update(meta.get("targets", {}))
        if meta.get("prompt_mode") == "replace":
            merged["body"] = soul["body"]
        else:
            merged["body"] = (merged["body"] + "\n\n" + soul["body"]).strip()
        merged["metadata"].update(meta)

    return merged


def seed_registry():
    """Copy bundled souls to the local registry."""
    LOCAL_REGISTRY.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_DIR.exists():
        return
    for path in REGISTRY_DIR.glob("*.md"):
        target = LOCAL_REGISTRY / path.name
        if not target.exists():
            import shutil
            shutil.copy2(path, target)


def create_soul(soul_id: str, from_soul: Optional[str] = None, voice: str = "shawn-builder") -> Path:
    """Create a new soul file in the local registry."""
    target = LOCAL_REGISTRY / f"{soul_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    derived_line = f'derived_from: {from_soul}' if from_soul else 'derived_from: null'

    content = f"""---
soul: {soul_id}
version: 0.1.0
{derived_line}
voice: {voice}@1.0.0
description: ""
authors: []
tags: []
targets:
  latency_p50_ms: 2000
  latency_p95_ms: 5000
  slop_score_floor: 92
  task_types: [general]
antislop:
  profile: strict
  overrides: {{}}
tools:
  allowed: "*"
  denied: []
changelog:
  - 0.1.0: "Initial release."
---

# {soul_id.replace('-', ' ').title()}

[Edit this prompt body. It will be loaded verbatim into the system prompt when this soul is active.]
"""
    target.write_text(content)
    return target


def create_soul_from_content(soul_id: str, content: str, voice: str = "shawn-builder") -> Path:
    """Create a soul from raw content (used for Hermes migration)."""
    target = LOCAL_REGISTRY / f"{soul_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    full = f"""---
soul: {soul_id}
version: 0.1.0
derived_from: null
voice: {voice}@1.0.0
description: "Migrated from Hermes SOUL.md"
authors: []
tags: [migrated]
targets:
  latency_p50_ms: 2000
  latency_p95_ms: 5000
  slop_score_floor: 90
  task_types: [general]
antislop:
  profile: balanced
  overrides: {{}}
changelog:
  - 0.1.0: "Migrated from Hermes."
---

{content}
"""
    target.write_text(full)
    return target


def body_sha256(text: str) -> str:
    """Compute SHA-256 hash of soul body text."""
    return hashlib.sha256(text.encode()).hexdigest()
