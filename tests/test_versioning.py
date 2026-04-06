"""Tests for the versioning system."""

from nio.core.versioning import bump_semver


def test_bump_patch():
    assert bump_semver("0.1.0", "patch") == "0.1.1"


def test_bump_minor():
    assert bump_semver("0.1.5", "minor") == "0.2.0"


def test_bump_major():
    assert bump_semver("1.2.3", "major") == "2.0.0"


def test_bump_from_zero():
    assert bump_semver("0.0.0", "patch") == "0.0.1"
    assert bump_semver("0.0.0", "minor") == "0.1.0"
    assert bump_semver("0.0.0", "major") == "1.0.0"
