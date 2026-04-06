"""Voice profile loader and runtime enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import frontmatter

NIO_HOME = Path.home() / ".nio"
REGISTRY_DIR = Path(__file__).parent.parent.parent / "registry" / "voice-profiles"
LOCAL_REGISTRY = NIO_HOME / "registry" / "voice-profiles"


@dataclass
class Detection:
    id: str
    tier: str
    description: str
    matches: list[str] = field(default_factory=list)


@dataclass
class VoiceResult:
    cleaned_text: str
    score: float
    detections: list[Detection] = field(default_factory=list)


def load_voice(voice_ref: str) -> Optional[dict]:
    """Load a voice profile by reference (id or id@version)."""
    if "@" in voice_ref:
        voice_id, version = voice_ref.split("@", 1)
        return _load_from_db(voice_id, version)

    path = _find_voice(voice_ref)
    if not path:
        return None

    post = frontmatter.load(path)
    return {
        "metadata": dict(post.metadata),
        "body": post.content,
        "raw": path.read_text(),
        "voice": post.metadata.get("voice", voice_ref),
        "version": post.metadata.get("version", "0.0.0"),
        "description": post.metadata.get("description", ""),
        "banned_phrases": post.metadata.get("banned_phrases", []),
        "antislop_rules": post.metadata.get("antislop_rules", {}),
        "tone": post.metadata.get("tone", {}),
    }


def _find_voice(voice_id: str) -> Optional[Path]:
    for registry in [LOCAL_REGISTRY, REGISTRY_DIR]:
        path = registry / f"{voice_id}.md"
        if path.exists():
            return path
    return None


def _load_from_db(voice_id: str, version: str) -> Optional[dict]:
    from nio.core.db import get_connection
    import json

    conn = get_connection()
    row = conn.execute(
        "SELECT body, rules FROM voice_versions WHERE voice_id = ? AND version = ?",
        (voice_id, version),
    ).fetchone()
    conn.close()

    if not row:
        return None

    rules = json.loads(row[1])
    return {
        "metadata": rules,
        "body": row[0],
        "raw": row[0],
        "voice": voice_id,
        "version": version,
        "description": rules.get("description", ""),
        "banned_phrases": rules.get("banned_phrases", []),
        "antislop_rules": rules.get("antislop_rules", {}),
        "tone": rules.get("tone", {}),
    }


def list_voices() -> list[dict]:
    """List all available voice profiles."""
    voices = []
    for registry in [LOCAL_REGISTRY, REGISTRY_DIR]:
        if not registry.exists():
            continue
        for path in sorted(registry.glob("*.md")):
            try:
                post = frontmatter.load(path)
                voices.append({
                    "voice": post.metadata.get("voice", path.stem),
                    "version": post.metadata.get("version", "0.0.0"),
                    "description": post.metadata.get("description", ""),
                    "path": str(path),
                })
            except Exception:
                continue
    seen = set()
    unique = []
    for v in voices:
        if v["voice"] not in seen:
            seen.add(v["voice"])
            unique.append(v)
    return unique


def get_active_voice() -> Optional[str]:
    """Return the active voice reference."""
    active_file = NIO_HOME / "active" / "voice.txt"
    if active_file.exists():
        return active_file.read_text().strip()
    return None


def set_active_voice(voice_id: str):
    """Set the active voice profile."""
    active_file = NIO_HOME / "active" / "voice.txt"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    voice = load_voice(voice_id)
    if voice:
        ref = f"{voice['voice']}@{voice['version']}"
    else:
        ref = voice_id
    active_file.write_text(ref)


def apply(voice_profile: dict, text: str) -> VoiceResult:
    """Apply voice profile rules to agent output text.

    1. Hard replace/reject banned_phrases
    2. Run anti-slop validator with the profile's rule set
    3. Return cleaned text + score + detections
    """
    cleaned = text
    detections = []

    # Step 1: Banned phrases
    for phrase in voice_profile.get("banned_phrases", []):
        if phrase.lower() in cleaned.lower():
            # Record detection
            detections.append(Detection(
                id="banned_phrase",
                tier="critical",
                description=f"Banned phrase: '{phrase}'",
                matches=[phrase],
            ))
            # Remove the phrase (case-insensitive)
            import re
            cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)

    # Step 2: Anti-slop validation
    from nio.core.antislop import detect, score

    antislop_detections = detect(cleaned)
    antislop_score = score(cleaned)

    for d in antislop_detections:
        detections.append(Detection(
            id=d["id"],
            tier=d["tier"],
            description=d["description"],
            matches=d.get("matches", []),
        ))

    return VoiceResult(
        cleaned_text=cleaned,
        score=antislop_score,
        detections=detections,
    )


def seed_voices():
    """Copy bundled voice profiles to the local registry."""
    LOCAL_REGISTRY.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_DIR.exists():
        return
    for path in REGISTRY_DIR.glob("*.md"):
        target = LOCAL_REGISTRY / path.name
        if not target.exists():
            import shutil
            shutil.copy2(path, target)
