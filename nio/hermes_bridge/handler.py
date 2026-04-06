"""Hermes hook handler shim.

Installed to ~/.hermes/hooks/nio/handler.py during `nio install`.
This is the thin entry point that Hermes discovers and calls.
"""

import sys
import os

sys.path.insert(0, os.path.expanduser("~/.nio/lib"))

from nio.hermes_bridge.middleware import handle as nio_handle  # noqa: E402


async def handle(event_type, context):
    return await nio_handle(event_type, context)
