"""NIO terminal boot sequence.

Donkey Kong-style: boss throws 429 rate limits, NIO climbs ladders,
dodges barrels, charges boss, victory with memory stats.
"""

from __future__ import annotations

import os
import sys
import time

G = "\033[38;2;78;195;115m"     # green
B = "\033[38;2;110;220;150m"    # bright green
D = "\033[38;2;55;65;75m"       # dim
W = "\033[38;2;230;237;243m"    # white
RED = "\033[38;2;239;68;68m"    # red
YEL = "\033[38;2;234;179;8m"    # yellow
CYN = "\033[38;2;56;189;248m"   # cyan
R = "\033[0m"                   # reset
BOLD = "\033[1m"
CLR = "\033[2J\033[H"
HIDE = "\033[?25l"
SHOW = "\033[?25h"


def _at(r, c, text):
    sys.stdout.write(f"\033[{r};{c}H{text}")


# --- Characters ---
SPRITE = [f"{B}▄█▄{R}", f"{B}▐█▌{R}", f"{B}▀ ▀{R}"]
SPRITE_JUMP = [f"{YEL}▄█▄{R}", f"{YEL}▐█▌{R}", f"{YEL}▀ ▀{R}"]

BOSS = [
    f"{RED}╔═══╗{R}",
    f"{RED}║{YEL}429{RED}║{R}",
    f"{RED}╚═══╝{R}",
]

BARREL = f"{RED}[429]{R}"
BARREL_CLEAR = "     "

TITLE = f"""{BOLD}{G}  ███╗   ██╗ ██╗  ██████╗
  ████╗  ██║ ██║ ██╔═══██╗
  ██╔██╗ ██║ ██║ ██║   ██║
  ██║╚██╗██║ ██║ ██║   ██║
  ██║ ╚████║ ██║ ╚██████╔╝
  ╚═╝  ╚═══╝ ╚═╝  ╚═════╝{R}"""

# DK-style platforms with ladders
# 3 platforms connected by ladders on alternating sides
PLATFORM_W = 54

SCN = 9  # scene start row

def _draw_platform(row, label_left="", label_right=""):
    """Draw a solid girder platform."""
    girder = f"{G}{'═' * PLATFORM_W}{R}"
    _at(row, 3, girder)
    if label_left:
        _at(row - 1, 5, f"{D}{label_left}{R}")
    if label_right:
        _at(row - 1, PLATFORM_W - len(label_right) + 1, f"{D}{label_right}{R}")


def _draw_ladder(top_row, bottom_row, col):
    """Draw a vertical ladder between two platforms."""
    for r in range(top_row + 1, bottom_row):
        _at(r, col, f"{D}╎H╎{R}")


def _draw_scene():
    """Draw the full DK-style scene: 3 platforms + 2 ladders."""
    # Platform 3 (top) - row SCN+1
    _draw_platform(SCN + 1, "~/.nio/nio.db", "SQLite+WAL")

    # Platform 2 (middle) - row SCN+6
    _draw_platform(SCN + 6, "sessions  turns", "soul_versions")

    # Platform 1 (bottom) - row SCN+11
    _draw_platform(SCN + 11, "slop_score  latency", "memory_context")

    # Floor
    _at(SCN + 14, 3, f"{D}{'─' * PLATFORM_W}{R}")

    # Ladder: right side connecting floor to platform 1
    _draw_ladder(SCN + 11, SCN + 14, 50)

    # Ladder: left side connecting platform 1 to platform 2
    _draw_ladder(SCN + 6, SCN + 11, 8)

    # Ladder: right side connecting platform 2 to platform 3
    _draw_ladder(SCN + 1, SCN + 6, 50)


# Climb path: floor -> ladder up -> run left -> ladder up -> run right -> ladder up -> top
CLIMB = [
    (SCN + 13, 5),        # start on floor left
    (SCN + 13, 48),       # run right to ladder
    (SCN + 10, 48),       # climb ladder (floor -> P1)
    (SCN + 10, 10),       # run left to ladder
    (SCN + 5, 10),        # climb ladder (P1 -> P2)
    (SCN + 5, 48),        # run right to ladder
    (SCN + 0, 48),        # climb ladder (P2 -> top)
]

BARRELS = [
    (46, 1, 12),    # barrel drops right while sprite runs
    (12, 3, 46),    # barrel drops left, sprite already right
    (46, 5, 12),    # barrel drops right, sprite dodges left
    (28, 6, 46),    # barrel drops center, sprite dodges right
]


def _draw_sprite(row, col):
    for j, s in enumerate(SPRITE):
        _at(row + j, col, s)


def _draw_sprite_jump(row, col):
    for j, s in enumerate(SPRITE_JUMP):
        _at(row + j, col, s)


def _clear_sprite(row, col):
    for j in range(3):
        _at(row + j, col, "   ")


def _draw_boss(row, col):
    for j, line in enumerate(BOSS):
        _at(row + j, col, line)


def _clear_boss(row, col):
    for j in range(3):
        _at(row + j, col, "     ")


def _drop_barrel(col, start_row, end_row):
    """Animate a 429 barrel falling."""
    for r in range(start_row, end_row + 1, 2):
        if r > start_row:
            _at(r - 2, col, BARREL_CLEAR)
        _at(r, col, BARREL)
        sys.stdout.flush()
        time.sleep(0.02)
    _at(end_row, col, BARREL_CLEAR)
    sys.stdout.flush()


def _dodge_jump(row, from_col, to_col):
    """Sprite hops sideways to dodge."""
    _clear_sprite(row, from_col)
    _draw_sprite_jump(row - 1, to_col)
    sys.stdout.flush()
    time.sleep(0.06)
    _clear_sprite(row - 1, to_col)
    _draw_sprite(row, to_col)
    sys.stdout.flush()
    time.sleep(0.04)


def _slide(from_col, to_col, row):
    """Smooth horizontal movement."""
    step = 3 if to_col > from_col else -3
    c = from_col
    while True:
        _clear_sprite(row, c)
        c += step
        if (step > 0 and c >= to_col) or (step < 0 and c <= to_col):
            c = to_col
            _draw_sprite(row, c)
            sys.stdout.flush()
            break
        _draw_sprite(row, c)
        sys.stdout.flush()
        time.sleep(0.015)


def _climb(from_row, to_row, col):
    """Climb up a ladder."""
    d = -1 if to_row < from_row else 1
    r = from_row
    while r != to_row:
        _clear_sprite(r, col)
        r += d
        _draw_sprite(r, col)
        sys.stdout.flush()
        time.sleep(0.025)


def _get_memory_stats():
    try:
        from nio.core.db import get_connection
        conn = get_connection()
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        turns = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        conn.close()
        return sessions, turns
    except Exception:
        return 0, 0


def boot_animated():
    """Run the DK-style boot animation."""
    try:
        ts = os.get_terminal_size()
        if ts.columns < 60 or ts.lines < 28:
            boot_static()
            return
    except OSError:
        boot_static()
        return

    sys.stdout.write(HIDE + CLR)
    sys.stdout.flush()

    try:
        # --- Title ---
        sys.stdout.write(f"\033[1;1H{TITLE}")
        _at(7, 3, f"{D}context engineering for CLI agents.{R}")
        sys.stdout.flush()
        time.sleep(0.3)

        # --- Draw scene ---
        _draw_scene()
        sys.stdout.flush()
        time.sleep(0.15)

        # --- Boss appears top-left ---
        boss_row, boss_col = SCN - 1, 5
        _draw_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.2)

        # Boss shakes
        for _ in range(3):
            _draw_boss(boss_row, boss_col + 1)
            sys.stdout.flush()
            time.sleep(0.04)
            _draw_boss(boss_row, boss_col - 1)
            sys.stdout.flush()
            time.sleep(0.04)
        _draw_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.1)

        # --- NIO climbs ---
        barrel_idx = 0
        prev_row, prev_col = CLIMB[0]
        _draw_sprite(prev_row, prev_col)
        sys.stdout.flush()
        time.sleep(0.1)

        for step_i in range(1, len(CLIMB)):
            stop_row, stop_col = CLIMB[step_i]

            # Boss throws barrel?
            if barrel_idx < len(BARRELS):
                bcol, btrigger, dodge_col = BARRELS[barrel_idx]
                if step_i == btrigger:
                    # Boss shakes
                    _draw_boss(boss_row, boss_col + 1)
                    sys.stdout.flush()
                    time.sleep(0.03)
                    _draw_boss(boss_row, boss_col)

                    # Dodge if nearby
                    if abs(prev_col - bcol) < 12:
                        _dodge_jump(prev_row, prev_col, dodge_col)
                        prev_col = dodge_col

                    _drop_barrel(bcol, SCN, SCN + 13)
                    barrel_idx += 1

            # Move
            if stop_row == prev_row:
                _slide(prev_col, stop_col, stop_row)
            else:
                _climb(prev_row, stop_row, prev_col)
                if stop_col != prev_col:
                    prev_row = stop_row
                    _slide(prev_col, stop_col, stop_row)

            prev_row, prev_col = stop_row, stop_col

        time.sleep(0.1)

        # --- Charge boss ---
        _slide(prev_col, 14, prev_row)
        prev_col = 14
        time.sleep(0.05)

        # Impact flash
        _draw_sprite_jump(prev_row, prev_col)
        sys.stdout.flush()
        time.sleep(0.06)
        _draw_sprite(prev_row, prev_col)

        # Boss gets hit and falls
        for offset in range(1, 7):
            _clear_boss(boss_row + offset - 1, max(1, boss_col - (offset - 1) * 2))
            new_r = boss_row + offset
            new_c = max(1, boss_col - offset * 2)
            if new_r < SCN + 14:
                _draw_boss(new_r, new_c)
            sys.stdout.flush()
            time.sleep(0.03)
        _clear_boss(boss_row + 6, max(1, boss_col - 12))
        sys.stdout.flush()

        time.sleep(0.15)

        # --- Victory ---
        _slide(prev_col, 24, prev_row)

        _at(8, 10, f"{BOLD}{B}  ETERNAL MEMORY LOADED  {R}")
        sys.stdout.flush()
        time.sleep(0.3)

        # Context drops
        drops = [
            (SCN - 2, 5, f"{B}◆{G} soul{R}"),
            (SCN - 2, 15, f"{B}◆{G} voice{R}"),
            (SCN - 2, 27, f"{B}◆{G} memory{R}"),
            (SCN - 2, 40, f"{B}◆{G} anti-slop{R}"),
        ]
        for dr, dc, dlabel in drops:
            _at(dr, dc, dlabel)
            sys.stdout.flush()
            time.sleep(0.07)

        # Memory stats
        sessions, turns = _get_memory_stats()
        if sessions > 0:
            _at(SCN + 15, 3, f"{D}sessions: {W}{sessions}{D}  turns: {W}{turns}{D}  memory: {B}eternal{R}")
        else:
            _at(SCN + 15, 3, f"{D}first run. memory starts now.{R}")
        sys.stdout.flush()

        time.sleep(0.3)
        _at(SCN + 17, 1, "")
        sys.stdout.flush()

    finally:
        sys.stdout.write(SHOW)
        sys.stdout.flush()

    print()


def boot_status(soul: str, voice: str, slop: str, dash: str, hermes: str):
    """Print status readout."""
    print(f"  {BOLD}{G}soul:{R}    {W}{soul}{R}")
    print(f"  {BOLD}{G}voice:{R}   {W}{voice}{R}")
    print(f"  {BOLD}{G}slop:{R}    {W}{slop}{R}")
    print(f"  {BOLD}{G}dash:{R}    {W}{dash}{R}")
    print(f"  {BOLD}{G}hermes:{R}  {W}{hermes}{R}")
    print()


def boot_static():
    """Non-animated fallback."""
    print(TITLE)
    print(f"  {D}context engineering for CLI agents.{R}")
    print()
    sessions, turns = _get_memory_stats()
    if sessions > 0:
        print(f"  {D}sessions: {W}{sessions}{D}  turns: {W}{turns}{D}  memory: {B}eternal{R}")
    else:
        print(f"  {D}first run. memory starts now.{R}")
    print()
