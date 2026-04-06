"""NIO terminal boot sequence.

Renders animated ASCII art directly in the terminal:
- NIO sprite evolves through 5 tiers
- DB scaffold builds up (DK platforms)
- Final form climbs through the tables
- Context items drop in
- Status readout
"""

from __future__ import annotations

import sys
import time
import os

# --- Colors (ANSI true color) ---
GREEN = "\033[38;2;78;195;115m"
BRIGHT = "\033[38;2;110;220;150m"
DIM = "\033[38;2;72;79;88m"
WHITE = "\033[38;2;230;237;243m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


def _goto(row: int, col: int) -> str:
    return f"\033[{row};{col}H"


# --- Sprites (5 tiers, each 9 lines) ---
TIER_1 = [
    "     ▄▄     ",
    "    ▐██▌    ",
    "    ▐██▌    ",
    "   ▄████▄   ",
    "   ▐████▌   ",
    "    ▐██▌    ",
    "    ▐██▌    ",
    "   ▐▌  ▐▌   ",
    "   ▀▀  ▀▀   ",
]

TIER_2 = [
    "     ▄█▄    ",
    "    ▐███▌   ",
    "    ▐███▌   ",
    "  ▄▐████▌   ",
    "  █▐████▌▄  ",
    "   ▐████▌█  ",
    "    ▐██▌    ",
    "   ▐██ ██▌  ",
    "   ▀▀  ▀▀   ",
]

TIER_3 = [
    "    ▄███▄   ",
    "   ▐█████▌  ",
    "   ▐█████▌  ",
    " ▄▌██████▐▄ ",
    " █▌██████▐█ ",
    "  ▐██████▌  ",
    "   ▐████▌   ",
    "  ▐██  ██▌  ",
    "  ▀▀▀  ▀▀▀  ",
]

TIER_4 = [
    "   ✦▄███▄✦  ",
    "  ✦▐█████▌✦ ",
    "   ▐█████▌  ",
    "·▄▌██████▐▄·",
    " █▌██████▐█ ",
    "·▐████████▌·",
    "  ▐██████▌  ",
    "  ▐██  ██▌  ",
    "  ▀▀▀  ▀▀▀  ",
]

TIER_5 = [
    " ✦ ◆▄███▄◆ ✦",
    " ✧▐███████▌✧",
    "  ▐███████▌ ",
    "◆▄▌████████▄◆",
    " █▌████████▐█",
    "◆▐██████████▌◆",
    "  ▐████████▌ ",
    "  ▐███  ███▌ ",
    "  ▀▀▀▀ ▀▀▀▀ ",
]

TIERS = [TIER_1, TIER_2, TIER_3, TIER_4, TIER_5]
TIER_LABELS = ["spark", "scout", "builder", "architect", "alchemist"]

# --- DB Scaffold ---
DB_SCAFFOLD = [
    ("┌──────────────────────────────────────────────────────┐", GREEN),
    ("│  ~/.nio/nio.db                          SQLite + WAL │", None),
    ("├──────────────────────────────────────────────────────┤", GREEN),
    ("│ ┌──────────┐  ┌──────────────┐  ┌────────────────┐  │", DIM),
    ("│ │team_state│  │voice_versions│  │  schema_info   │  │", DIM),
    ("│ └──────────┘  └──────────────┘  └────────────────┘  │", DIM),
    ("│══════════════════════════════════════════════════════│", GREEN),
    ("│ ┌──────────┐  ┌──────────────┐  ┌────────────────┐  │", DIM),
    ("│ │ sessions │  │    turns     │  │ soul_versions  │  │", DIM),
    ("│ └──────────┘  └──────────────┘  └────────────────┘  │", DIM),
    ("│══════════════════════════════════════════════════════│", GREEN),
    ("│  slop_score    latency_ms       body_sha256         │", DIM),
    ("│  user_msg      slop_violations  frontmatter         │", DIM),
    ("│══════════════════════════════════════════════════════│", GREEN),
    ("└──────────────────────────────────────────────────────┘", GREEN),
]

NIO_TITLE = [
    "  ███╗   ██╗ ██╗  ██████╗ ",
    "  ████╗  ██║ ██║ ██╔═══██╗",
    "  ██╔██╗ ██║ ██║ ██║   ██║",
    "  ██║╚██╗██║ ██║ ██║   ██║",
    "  ██║ ╚████║ ██║ ╚██████╔╝",
    "  ╚═╝  ╚═══╝ ╚═╝  ╚═════╝ ",
]


def _print_at(row: int, col: int, text: str, color: str = GREEN):
    sys.stdout.write(f"{_goto(row, col)}{color}{text}{RESET}")


def _draw_sprite(start_row: int, col: int, sprite: list[str], color: str = GREEN):
    for i, line in enumerate(sprite):
        _print_at(start_row + i, col, line, f"{BOLD}{color}")


def _draw_title(start_row: int):
    for i, line in enumerate(NIO_TITLE):
        _print_at(start_row + i, 14, line, f"{BOLD}{GREEN}")


def _draw_db(start_row: int, up_to: int = -1):
    lines = DB_SCAFFOLD if up_to < 0 else DB_SCAFFOLD[:up_to]
    for i, (line, color) in enumerate(lines):
        c = color or f"{GREEN}"
        # Colorize table names
        styled = line
        for tbl in ["sessions", "turns", "soul_versions", "voice_versions", "team_state", "schema_info"]:
            if tbl in styled:
                styled = styled.replace(tbl, f"{WHITE}{tbl}{c}")
        _print_at(start_row + i, 2, styled, c)


def boot_animated():
    """Run the full animated boot sequence in terminal."""
    try:
        rows = os.get_terminal_size().lines
        cols = os.get_terminal_size().columns
    except OSError:
        boot_static()
        return

    if cols < 60 or rows < 35:
        boot_static()
        return

    sys.stdout.write(HIDE_CURSOR + CLEAR)
    sys.stdout.flush()

    try:
        # --- Phase 1: Title ---
        _draw_title(2)
        _print_at(9, 6, "voice DNA. semver souls. anti-slop.", DIM)
        _print_at(10, 6, "the layer hermes never had.", DIM)
        sys.stdout.flush()
        time.sleep(0.6)

        # --- Phase 2: Evolution ---
        sprite_row = 22
        sprite_col = 22

        for i, (sprite, label) in enumerate(zip(TIERS, TIER_LABELS)):
            # Clear previous sprite area
            for r in range(sprite_row, sprite_row + 12):
                _print_at(r, sprite_col - 2, " " * 20, "")

            _draw_sprite(sprite_row, sprite_col, sprite)
            _print_at(sprite_row + 10, sprite_col + 1, f"[ {label} ]", DIM)
            sys.stdout.flush()

            if i < 4:
                time.sleep(0.45)
            else:
                # Flash on final evolution
                time.sleep(0.15)
                _draw_sprite(sprite_row, sprite_col, sprite, BRIGHT)
                sys.stdout.flush()
                time.sleep(0.15)
                _draw_sprite(sprite_row, sprite_col, sprite, GREEN)
                sys.stdout.flush()
                time.sleep(0.3)

        time.sleep(0.3)

        # --- Phase 3: DB scaffold builds up ---
        db_start = 12
        for i in range(1, len(DB_SCAFFOLD) + 1):
            _draw_db(db_start, up_to=i)
            sys.stdout.flush()
            time.sleep(0.06)

        time.sleep(0.3)

        # --- Phase 4: Sprite climbs up through DB ---
        positions = [30, 27, 24, 21, 18, 15]
        for pos in positions:
            # Clear old position
            for r in range(pos + 3, pos + 12):
                _print_at(r, sprite_col - 2, " " * 20, "")
            _draw_sprite(pos, sprite_col, TIER_5)
            sys.stdout.flush()
            time.sleep(0.12)

        # Clear label from evolution
        _print_at(sprite_row + 10, sprite_col - 2, " " * 20, "")

        time.sleep(0.2)

        # --- Phase 5: Context drops ---
        drops = [
            (12, 3, "◆ soul"),
            (12, 18, "◆ voice"),
            (12, 34, "◆ memory"),
            (12, 48, "◆ slop"),
        ]
        for _, dc, dlabel in drops:
            _print_at(11, dc, dlabel, BRIGHT)
            sys.stdout.flush()
            time.sleep(0.15)

        time.sleep(0.4)

        # --- Phase 6: Status readout ---
        _print_at(30, 2, "━" * 54, GREEN)

        sys.stdout.flush()

    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    # Move cursor below the animation
    print(_goto(32, 1))


def boot_status(soul: str, voice: str, slop: str, dash: str, hermes: str):
    """Print the status readout (after animation or standalone)."""
    lines = [
        f"  {BOLD}{GREEN}soul:{RESET}    {WHITE}{soul}{RESET}",
        f"  {BOLD}{GREEN}voice:{RESET}   {WHITE}{voice}{RESET}",
        f"  {BOLD}{GREEN}slop:{RESET}    {WHITE}{slop}{RESET}",
        f"  {BOLD}{GREEN}dash:{RESET}    {WHITE}{dash}{RESET}",
        f"  {BOLD}{GREEN}hermes:{RESET}  {WHITE}{hermes}{RESET}",
    ]
    print()
    for line in lines:
        print(line)
    print()


def boot_static():
    """Non-animated fallback for small terminals or piped output."""
    print()
    for line in NIO_TITLE:
        print(f"{BOLD}{GREEN}{line}{RESET}")
    print()
    print(f"{DIM}  voice DNA. semver souls. anti-slop.{RESET}")
    print(f"{DIM}  the layer hermes never had.{RESET}")
    print()
    for sprite_line in TIER_5:
        print(f"  {BOLD}{GREEN}{sprite_line}{RESET}")
    print()
