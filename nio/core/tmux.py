"""Persistent Claude Code sessions via tmux.

Manages a background tmux session running Claude Code with the active soul.
Session survives terminal close. Reconnect with: tmux attach -t nio
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SESSION_NAME = "nio"
CLAUDE_BIN = "/opt/homebrew/bin/claude"
NIO_HOME = Path.home() / ".nio"


def _write_soul_prompt() -> Path:
    """Write the active soul body to a temp file for --append-system-prompt-file."""
    prompt_path = NIO_HOME / "active" / "soul-prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from nio.core.soul import get_active_soul, load_soul
        ref = get_active_soul() or ""
        soul_id = ref.split("@")[0] if ref else ""
        if soul_id:
            data = load_soul(soul_id)
            if data and data.get("body"):
                prompt_path.write_text(data["body"])
                return prompt_path
    except Exception:
        pass

    # Fallback: empty prompt
    if not prompt_path.exists():
        prompt_path.write_text("")
    return prompt_path


def is_running() -> bool:
    """Check if the NIO tmux session is alive."""
    result = subprocess.run(
        ["tmux", "has-session", "-t", SESSION_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def start_session() -> bool:
    """Start a tmux session running Claude Code with the active soul.

    Returns True if session was created, False if already running.
    """
    if is_running():
        return False

    soul_path = _write_soul_prompt()

    cmd = (
        f'{CLAUDE_BIN} --append-system-prompt-file "{soul_path}"'
    )

    subprocess.run(
        ["tmux", "new-session", "-d", "-s", SESSION_NAME, "-c", str(Path.home()), cmd],
        capture_output=True,
    )
    return is_running()


def kill_session() -> bool:
    """Kill the NIO tmux session."""
    if not is_running():
        return False
    subprocess.run(
        ["tmux", "kill-session", "-t", SESSION_NAME],
        capture_output=True,
    )
    return True


def send_command(text: str):
    """Send a command to the running NIO tmux session."""
    if not is_running():
        return
    subprocess.run(
        ["tmux", "send-keys", "-t", SESSION_NAME, text, "Enter"],
        capture_output=True,
    )
