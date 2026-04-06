"""Tests for the Hermes bridge middleware."""


def test_middleware_import():
    """Verify the middleware module imports cleanly."""
    from nio.hermes_bridge.middleware import handle
    assert callable(handle)
