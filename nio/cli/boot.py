"""NIO terminal boot sequence.

Donkey Kong-style: boss throws 429 rate limits, NIO dodges and climbs.
"""

from __future__ import annotations

import sys
import time
import os

G = "\033[38;2;78;195;115m"     # green
B = "\033[38;2;110;220;150m"    # bright green
D = "\033[38;2;55;65;75m"       # dim
W = "\033[38;2;230;237;243m"    # white
RED = "\033[38;2;239;68;68m"    # red
YEL = "\033[38;2;234;179;8m"    # yellow
R = "\033[0m"                   # reset
BOLD = "\033[1m"
CLR = "\033[2J\033[H"
HIDE = "\033[?25l"
SHOW = "\033[?25h"


def _at(r, c, text):
    sys.stdout.write(f"\033[{r};{c}H{text}")


# --- Characters ---
SPRITE = [f"{B}▄█▄{R}", f"{B}▐█▌{R}", f"{B}▀ ▀{R}"]

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

SCENE = [
    f"{G}  ╔═══════════════════════════════════════════════════╗{R}",       # row 0
    f"{G}  ║{R} {W}~/.nio/nio.db{R}                        {D}SQLite+WAL{R} {G}║{R}",  # row 1
    f"{G}  ╠═══════════════════════════════════════════════════╣{R}",       # row 2
    f"{G}  ║{R}  {D}┌──────────┐  ┌────────────┐  ┌────────────┐{R} {G}║{R}",  # row 3
    f"{G}  ║{R}  {D}│{W}team_state{D}│  │{W}voice_versns{D}│  │{W} schema_info{D}│{R} {G}║{R}",  # row 4
    f"{G}  ║{R}  {D}└──────────┘  └────────────┘  └────────────┘{R} {G}║{R}",  # row 5
    f"{G}  ║{B}══════════════════════════════════════════════════{G}║{R}",   # row 6 platform
    f"{G}  ║{R}  {D}┌──────────┐  ┌────────────┐  ┌────────────┐{R} {G}║{R}",  # row 7
    f"{G}  ║{R}  {D}│{W} sessions {D}│  │{W}    turns   {D}│  │{W}soul_version{D}│{R} {G}║{R}",  # row 8
    f"{G}  ║{R}  {D}└──────────┘  └────────────┘  └────────────┘{R} {G}║{R}",  # row 9
    f"{G}  ║{B}══════════════════════════════════════════════════{G}║{R}",   # row 10 platform
    f"{G}  ║{R}  {D}slop_score    latency_ms       body_sha256{R}  {G}║{R}",  # row 11
    f"{G}  ║{R}  {D}user_msg      slop_violations  frontmatter{R}  {G}║{R}",  # row 12
    f"{G}  ║{B}══════════════════════════════════════════════════{G}║{R}",   # row 13 platform
    f"{G}  ╚═══════════════════════════════════════════════════╝{R}",       # row 14
]

SCN = 9  # scene start row (row 9 in terminal)

# Zigzag stops: (terminal_row, col)
# Platform rows in terminal: bottom=SCN+13, mid=SCN+10, mid2=SCN+6, top=SCN+2
CLIMB = [
    # start bottom-left
    (SCN + 13, 5),
    # run right across bottom
    (SCN + 13, 28), (SCN + 13, 50),
    # climb right side
    (SCN + 10, 50),
    # run left across middle
    (SCN + 10, 28), (SCN + 10, 5),
    # climb left side
    (SCN + 6, 5),
    # run right across upper
    (SCN + 6, 28), (SCN + 6, 50),
    # climb to top
    (SCN + 2, 50),
    # run to boss
    (SCN + 2, 28),
]

# Barrel drops: (start_col, timing_index) - which climb step triggers each barrel
BARRELS = [
    (48, 1),   # boss throws right as NIO starts running
    (8, 3),    # throws left as NIO climbs right
    (48, 5),   # throws right as NIO runs left
    (8, 7),    # throws left as NIO runs right
    (28, 9),   # throws center on final climb
]


def _draw_sprite(row, col):
    for j, s in enumerate(SPRITE):
        _at(row + j, col, s)


def _clear_sprite(row, col):
    for j in range(3):
        _at(row + j, col, "   ")


def _draw_boss(row, col):
    for j, line in enumerate(BOSS):
        _at(row + j, col, line)


def _drop_barrel(col, start_row, end_row):
    """Animate a 429 barrel falling down."""
    for r in range(start_row, end_row + 1, 2):
        if r > start_row:
            _at(r - 2, col, BARREL_CLEAR)
        _at(r, col, BARREL)
        sys.stdout.flush()
        time.sleep(0.025)
    # Clear at bottom
    _at(end_row, col, BARREL_CLEAR)
    sys.stdout.flush()


def _slide(from_col, to_col, row):
    """Slide sprite horizontally across a platform."""
    step = 4 if to_col > from_col else -4
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
        time.sleep(0.02)


def _climb(from_row, to_row, col):
    """Climb sprite vertically."""
    direction = -1 if to_row < from_row else 1
    r = from_row
    while r != to_row:
        _clear_sprite(r, col)
        r += direction
        # Draw ladder rung
        _at(r + (2 if direction == -1 else 0), col + 1, f"{D}╎{R}")
        _draw_sprite(r, col)
        sys.stdout.flush()
        time.sleep(0.02)


def boot_animated():
    """Run the full DK-style boot animation."""
    try:
        ts = os.get_terminal_size()
        if ts.columns < 58 or ts.lines < 30:
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
        _at(7, 3, f"{D}voice DNA. semver souls. anti-slop.{R}")
        _at(8, 3, f"{D}the layer hermes never had.{R}")
        sys.stdout.flush()
        time.sleep(0.3)

        # --- DB scaffold ---
        for i, line in enumerate(SCENE):
            _at(SCN + i, 1, line)
            sys.stdout.flush()
            time.sleep(0.02)

        # --- Boss appears at top ---
        boss_row, boss_col = SCN - 1, 25
        _draw_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.3)

        # Boss shakes
        for _ in range(2):
            _draw_boss(boss_row, boss_col + 1)
            sys.stdout.flush()
            time.sleep(0.06)
            _draw_boss(boss_row, boss_col - 1)
            sys.stdout.flush()
            time.sleep(0.06)
        _draw_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.1)

        # --- NIO climbs with barrel dodging ---
        barrel_idx = 0
        prev_row, prev_col = CLIMB[0]
        _draw_sprite(prev_row, prev_col)
        sys.stdout.flush()
        time.sleep(0.1)

        for step_i in range(1, len(CLIMB)):
            stop_row, stop_col = CLIMB[step_i]

            # Check if boss should throw a barrel now
            if barrel_idx < len(BARRELS):
                bcol, btrigger = BARRELS[barrel_idx]
                if step_i == btrigger:
                    # Boss shakes and throws
                    _draw_boss(boss_row, boss_col + 1)
                    sys.stdout.flush()
                    time.sleep(0.04)
                    _draw_boss(boss_row, boss_col)

                    # Barrel falls (in background feel - quick)
                    _drop_barrel(bcol, SCN + 1, SCN + 13)
                    barrel_idx += 1

            # Move sprite
            if stop_row == prev_row:
                _slide(prev_col, stop_col, stop_row)
            else:
                _climb(prev_row, stop_row, prev_col)
                if stop_col != prev_col:
                    prev_row = stop_row
                    _slide(prev_col, stop_col, stop_row)

            prev_row, prev_col = stop_row, stop_col

        time.sleep(0.1)

        # --- NIO reaches boss: boss gets knocked off ---
        # Flash boss
        for j in range(3):
            _at(boss_row + j, boss_col, "     ")
        sys.stdout.flush()
        time.sleep(0.08)
        _draw_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.08)

        # Boss falls off right side
        for offset in range(1, 8):
            for j in range(3):
                _at(boss_row + j, boss_col, "     ")
            _draw_boss(boss_row + offset, boss_col + offset * 2)
            sys.stdout.flush()
            time.sleep(0.04)
        # Clear fallen boss
        for j in range(3):
            _at(boss_row + 7 + j, boss_col + 14, "     ")
        sys.stdout.flush()

        time.sleep(0.15)

        # --- Victory: context items appear ---
        drops = [
            (8, 4, f"{B}◆{G}soul{R}"),
            (8, 16, f"{B}◆{G}voice{R}"),
            (8, 29, f"{B}◆{G}memory{R}"),
            (8, 43, f"{B}◆{G}slop{R}"),
        ]
        for _, dc, dlabel in drops:
            _at(8, dc, dlabel)
            sys.stdout.flush()
            time.sleep(0.06)

        time.sleep(0.2)
        _at(26, 1, "")
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
    print(f"  {D}voice DNA. semver souls. anti-slop.{R}")
    print(f"  {D}the layer hermes never had.{R}")
    print()
    for line in SCENE:
        print(line)
    print()
