"""Tests for the soul loader, inheritance resolver, and versioning."""

import frontmatter
import pytest

# --- Soul loading ---

def test_list_souls_finds_bundled():
    from nio.core.soul import list_souls
    souls = list_souls()
    ids = [s["soul"] for s in souls]
    assert "nio-core" in ids
    assert "nio-reviewer" in ids


def test_load_nio_core():
    from nio.core.soul import load_soul
    soul = load_soul("nio-core")
    assert soul is not None
    assert soul["soul"] == "nio-core"
    assert soul["version"] == "0.1.0"
    assert soul["voice"] == "shawn-builder@1.0.0"
    assert "NIO Core" in soul["body"]


def test_load_nio_reviewer():
    from nio.core.soul import load_soul
    soul = load_soul("nio-reviewer")
    assert soul is not None
    assert soul["soul"] == "nio-reviewer"
    assert soul["metadata"]["derived_from"] == "nio-core"
    assert soul["metadata"]["targets"]["slop_score_floor"] == 95


def test_load_nonexistent_returns_none():
    from nio.core.soul import load_soul
    assert load_soul("does-not-exist") is None


def test_soul_frontmatter_schema():
    """Verify nio-core has all required frontmatter fields."""
    from nio.core.soul import load_soul
    soul = load_soul("nio-core")
    meta = soul["metadata"]
    assert "soul" in meta
    assert "version" in meta
    assert "voice" in meta
    assert "description" in meta
    assert "targets" in meta
    assert "antislop" in meta
    assert "slop_score_floor" in meta["targets"]


def test_soul_body_not_empty():
    from nio.core.soul import load_soul
    for soul_id in ["nio-core", "nio-reviewer"]:
        soul = load_soul(soul_id)
        assert len(soul["body"].strip()) > 100, f"{soul_id} body too short"


# --- Inheritance ---

def test_inheritance_merges_bodies():
    from nio.core.soul import resolve_soul_with_inheritance
    merged = resolve_soul_with_inheritance("nio-reviewer")
    assert "NIO Core" in merged["body"]
    assert "NIO Reviewer" in merged["body"]
    # nio-core body should come first (base)
    core_pos = merged["body"].index("NIO Core")
    reviewer_pos = merged["body"].index("NIO Reviewer")
    assert core_pos < reviewer_pos


def test_inheritance_overrides_targets():
    from nio.core.soul import resolve_soul_with_inheritance
    merged = resolve_soul_with_inheritance("nio-reviewer")
    assert merged["targets"]["slop_score_floor"] == 95
    # Latency targets come from child (override)
    assert merged["targets"]["latency_p50_ms"] == 3000


def test_inheritance_merges_antislop_overrides():
    from nio.core.soul import resolve_soul_with_inheritance
    merged = resolve_soul_with_inheritance("nio-reviewer")
    overrides = merged["antislop"].get("overrides", {})
    assert overrides.get("engagement_bait") == "strict"
    assert overrides.get("false_dichotomies") == "strict"


def test_inheritance_preserves_voice():
    from nio.core.soul import resolve_soul_with_inheritance
    merged = resolve_soul_with_inheritance("nio-reviewer")
    assert merged["voice"] == "shawn-builder@1.0.0"


def test_no_inheritance_for_base_soul():
    from nio.core.soul import resolve_soul_with_inheritance
    merged = resolve_soul_with_inheritance("nio-core")
    assert "NIO Core" in merged["body"]
    assert "NIO Reviewer" not in merged["body"]


def test_circular_inheritance_raises(tmp_path):
    """Circular derived_from chains should raise ValueError."""
    from nio.core import soul as soul_mod

    # Temporarily override registry dir
    orig_registry = soul_mod.REGISTRY_DIR
    soul_mod.REGISTRY_DIR = tmp_path

    # Create two souls that reference each other
    (tmp_path / "soul-a.md").write_text("""---
soul: soul-a
version: 0.1.0
derived_from: soul-b
voice: shawn-builder@1.0.0
---

Soul A body.
""")
    (tmp_path / "soul-b.md").write_text("""---
soul: soul-b
version: 0.1.0
derived_from: soul-a
voice: shawn-builder@1.0.0
---

Soul B body.
""")

    with pytest.raises(ValueError, match="Circular inheritance"):
        soul_mod.resolve_soul_with_inheritance("soul-a")

    # Restore
    soul_mod.REGISTRY_DIR = orig_registry


# --- Active soul ---

def test_set_and_get_active_soul(tmp_path):
    from nio.core import soul as soul_mod

    # Use tmp for active dir
    orig_home = soul_mod.NIO_HOME
    soul_mod.NIO_HOME = tmp_path

    soul_mod.set_active_soul("nio-core")
    result = soul_mod.get_active_soul()
    assert result == "nio-core@0.1.0"

    soul_mod.NIO_HOME = orig_home


# --- Voice loading ---

def test_list_voices():
    from nio.core.voice import list_voices
    voices = list_voices()
    ids = [v["voice"] for v in voices]
    assert "shawn-builder" in ids
    assert "enterprise-neutral" in ids


def test_load_voice_profile():
    from nio.core.voice import load_voice
    voice = load_voice("shawn-builder")
    assert voice is not None
    assert voice["voice"] == "shawn-builder"
    assert "game changer" in voice["banned_phrases"]
    assert voice["tone"]["register"] == "casual"
    assert voice["tone"]["authority"] == "earned"


def test_voice_apply_catches_banned_phrase():
    from nio.core.voice import apply, load_voice
    voice = load_voice("shawn-builder")
    result = apply(voice, "This tool is a game changer for GTM teams.")
    # Banned phrase is detected and removed from cleaned text
    banned_ids = [d.id for d in result.detections]
    assert "banned_phrase" in banned_ids
    assert "game changer" not in result.cleaned_text


def test_voice_apply_clean_text():
    from nio.core.voice import apply, load_voice
    voice = load_voice("shawn-builder")
    result = apply(voice, "I built a scoring model in SQLite. It updates the dashboard every hour.")
    assert result.score == 100.0


# --- Versioning ---

def test_release_soul_bumps_version(tmp_path):
    """Release creates a DB snapshot and bumps the file version."""
    from nio.core import db as db_mod
    from nio.core import soul as soul_mod
    from nio.core.versioning import release_soul

    # Use tmp paths to avoid touching real registry/DB
    orig_local = soul_mod.LOCAL_REGISTRY
    soul_mod.LOCAL_REGISTRY = tmp_path / "souls"
    soul_mod.LOCAL_REGISTRY.mkdir(parents=True)

    orig_db = db_mod.DB_PATH
    db_mod.DB_PATH = tmp_path / "test.db"
    db_mod.init_db()

    # Create a test soul
    soul_file = soul_mod.LOCAL_REGISTRY / "test-release.md"
    soul_file.write_text("""---
soul: test-release
version: 0.1.0
voice: shawn-builder@1.0.0
description: "Test"
---

Test body.
""")

    new_ver = release_soul("test-release", bump="minor", message="test bump")
    assert new_ver == "0.2.0"

    # Verify DB snapshot
    conn = db_mod.get_connection()
    row = conn.execute(
        "SELECT version FROM soul_versions WHERE soul_id = ?", ("test-release",)
    ).fetchone()
    conn.close()
    assert row[0] == "0.2.0"

    # Verify file updated
    post = frontmatter.load(soul_file)
    assert post.metadata["version"] == "0.2.0"

    # Restore
    soul_mod.LOCAL_REGISTRY = orig_local
    db_mod.DB_PATH = orig_db
