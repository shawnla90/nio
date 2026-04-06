"""NIO terminal boot sequence.

Donkey Kong-style visualization: NIO climbs through the DB layers.
Green terminal aesthetic. Shown on `nio install` and `nio status`.
"""

from __future__ import annotations

import sys
import time


# NIO pixel character (ASCII art, 7 lines tall)
NIO_SPRITE = [
    "    ▓▓    ",
    "   ▓██▓   ",
    "  ▓████▓  ",
    " ▓██▓▓██▓ ",
    "  ▓████▓▌ ",
    "   ▓██▓   ",
    "   ▓▓ ▓▓  ",
]

# DB scaffold layers (bottom to top, DK platforms)
DB_LAYERS = [
    ("═══════════════════════════════════════════════════════════════", None),
    ("  ┌─ team_state ─┐  ┌─ voice_versions ─┐  ┌─ schema_info ─┐ ", "dim"),
    ("══╪═══════════════╪══╪══════════════════╪══╪════════════════╪═", None),
    ("  ┌─ sessions ─┐  ┌─ turns ─────────────┐  ┌─ soul_versions─┐", "dim"),
    ("══╪════════════╪══╪═════════════════════╪══╪════════════════╪═", None),
    ("  │  slop_score │  │  latency_ms        │  │  body_sha256   │ ", "dim"),
    ("  │  user_msg   │  │  slop_violations   │  │  frontmatter   │ ", "dim"),
    ("══╪════════════╪══╪═════════════════════╪══╪════════════════╪═", None),
]

STATUS_LINES = [
    "  ~/.nio/nio.db                                     SQLite + WAL",
]


GREEN = "\033[38;2;78;195;115m"
DIM = "\033[38;2;72;79;88m"
WHITE = "\033[38;2;230;237;243m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K"


def _color(text: str, style: str | None = None) -> str:
    if style == "dim":
        return f"{DIM}{text}{RESET}"
    elif style == "white":
        return f"{WHITE}{text}{RESET}"
    elif style == "bold":
        return f"{BOLD}{GREEN}{text}{RESET}"
    return f"{GREEN}{text}{RESET}"


def boot_splash(animate: bool = True):
    """Show the NIO boot splash with DK-style DB visualization."""
    delay = 0.04 if animate else 0

    # Header
    print()
    print(_color("  ███╗   ██╗ ██╗  ██████╗ ", "bold"))
    print(_color("  ████╗  ██║ ██║ ██╔═══██╗", "bold"))
    print(_color("  ██╔██╗ ██║ ██║ ██║   ██║", "bold"))
    print(_color("  ██║╚██╗██║ ██║ ██║   ██║", "bold"))
    print(_color("  ██║ ╚████║ ██║ ╚██████╔╝", "bold"))
    print(_color("  ╚═╝  ╚═══╝ ╚═╝  ╚═════╝ ", "bold"))
    print()
    print(_color("  voice DNA. semver souls. anti-slop.", "dim"))
    print(_color("  the layer hermes never had.", "dim"))
    print()

    if animate:
        time.sleep(0.3)

    # DB scaffold (bottom-up, DK style)
    print(_color("  ┌──────────────────────────────────────────────────────────┐"))
    print(_color("  │", "") + _color(" ~/.nio/nio.db", "white") + _color("                               SQLite + WAL", "dim") + _color(" │"))
    print(_color("  ├──────────────────────────────────────────────────────────┤"))

    for line, style in DB_LAYERS:
        if animate:
            time.sleep(delay)
        print(_color(f"  │{line}│", style))

    print(_color("  └──────────────────────────────────────────────────────────┘"))

    if animate:
        time.sleep(0.2)

    # NIO character climbing up (appears at the side)
    print()
    for i, sprite_line in enumerate(NIO_SPRITE):
        if animate:
            time.sleep(delay)
        print(_color(f"  {sprite_line}", "bold") + ("  " + _color("< nio-core@0.1.0", "dim") if i == 2 else ""))

    print()


def boot_status(soul: str = "none", voice: str = "none", slop: str = "--", dash: str = ":4242", hermes: str = "--"):
    """Show the compact status line after boot."""
    print(_color("  ┌─────────────────────────────────────────────────┐"))
    print(_color("  │") + _color(" soul:", "bold") + f"  {WHITE}{soul}{RESET}" +
          _color("  │"))
    print(_color("  │") + _color(" voice:", "bold") + f" {WHITE}{voice}{RESET}" +
          _color("  │"))
    print(_color("  │") + _color(" slop:", "bold") + f"  {WHITE}{slop}{RESET}" +
          _color("  │"))
    print(_color("  │") + _color(" dash:", "bold") + f"  {WHITE}{dash}{RESET}" +
          _color("  │"))
    print(_color("  │") + _color(" hermes:", "bold") + f"{WHITE}{hermes}{RESET}" +
          _color("  │"))
    print(_color("  └─────────────────────────────────────────────────┘"))
    print()
