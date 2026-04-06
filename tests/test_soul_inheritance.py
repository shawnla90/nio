"""Tests for the soul loader and inheritance resolver."""

import pytest
from pathlib import Path


def test_load_soul_from_registry(tmp_path):
    """Test loading a soul from a file."""
    soul_file = tmp_path / "test-soul.md"
    soul_file.write_text("""---
soul: test-soul
version: 0.1.0
voice: shawn-builder@1.0.0
description: "Test soul"
---

# Test Soul

You are a test soul.
""")

    import frontmatter
    post = frontmatter.load(soul_file)
    assert post.metadata["soul"] == "test-soul"
    assert post.metadata["version"] == "0.1.0"
    assert "Test Soul" in post.content


def test_circular_inheritance_detected():
    """Circular derived_from chains should raise ValueError."""
    # This will be tested once we can inject mock souls
    pass
