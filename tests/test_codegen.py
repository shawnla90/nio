"""Tests for codegen renderers (Python, TypeScript, Markdown)."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def registry():
    """Load the anti-slop registry."""
    registry_path = Path(__file__).parent.parent / "registry" / "anti-slop.json"
    with open(registry_path) as f:
        return json.load(f)


def test_render_python_produces_valid_output(tmp_path, registry):
    from nio.codegen.render_python import render

    output_path = tmp_path / "antislop.py"
    render(target_path=output_path)

    assert output_path.exists()
    content = output_path.read_text()

    assert "def detect(" in content
    assert "def score(" in content
    assert "GENERATED" in content

    # Should be valid Python
    compile(content, str(output_path), "exec")


def test_render_python_has_all_rules(tmp_path, registry):
    from nio.codegen.render_python import render

    output_path = tmp_path / "antislop.py"
    render(target_path=output_path)

    content = output_path.read_text()
    regex_rules = [r for r in registry["rules"] if r["matcher"]["type"] == "regex"]
    for rule in regex_rules:
        assert rule["id"] in content, f"Rule {rule['id']} missing from generated Python"


def test_render_typescript_produces_valid_output(tmp_path, registry):
    from nio.codegen.render_typescript import render

    output_path = tmp_path / "anti-slop.ts"
    render(target_path=output_path)

    assert output_path.exists()
    content = output_path.read_text()

    assert "export" in content
    assert "GENERATED" in content


def test_render_typescript_has_rules(tmp_path, registry):
    from nio.codegen.render_typescript import render

    output_path = tmp_path / "anti-slop.ts"
    render(target_path=output_path)

    content = output_path.read_text()
    regex_rules = [r for r in registry["rules"] if r["matcher"]["type"] == "regex"]
    for rule in regex_rules:
        assert rule["id"] in content, f"Rule {rule['id']} missing from generated TypeScript"


def test_render_markdown_produces_output(tmp_path, registry):
    from nio.codegen.render_markdown import render

    output_path = tmp_path / "anti-slop-reference.md"
    render(target_path=output_path)

    assert output_path.exists()
    content = output_path.read_text()

    assert "critical" in content.lower()
    assert len(content) > 500


def test_render_markdown_covers_all_rules(tmp_path, registry):
    from nio.codegen.render_markdown import render

    output_path = tmp_path / "anti-slop-reference.md"
    render(target_path=output_path)

    content = output_path.read_text()
    for rule in registry["rules"]:
        assert rule["id"] in content, f"Rule {rule['id']} missing from generated Markdown"
