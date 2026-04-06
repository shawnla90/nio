"""NIO terminal boot sequence.

Donkey Kong-style: tiny sprite climbs up DB scaffold platforms.
Fast, clean, fits one screen.
"""

from __future__ import annotations

import sys
import time
import os

G = "\033[38;2;78;195;115m"    # green
B = "\033[38;2;110;220;150m"   # bright green
D = "\033[38;2;55;65;75m"      # dim
W = "\033[38;2;230;237;243m"   # white
R = "\033[0m"                  # reset
BOLD = "\033[1m"
CLR = "\033[2J\033[H"
HIDE = "\033[?25l"
SHOW = "\033[?25h"

def _at(r, c, text):
    sys.stdout.write(f"\033[{r};{c}H{text}")

# Tiny sprite (3 lines)
SPRITE = [f"{B}▄█▄{R}", f"{B}▐█▌{R}", f"{B}▀ ▀{R}"]

# Scene: 24 rows. Sprite climbs right edge via ladders.
TITLE = f"""{BOLD}{G}  ███╗   ██╗ ██╗  ██████╗
  ████╗  ██║ ██║ ██╔═══██╗
  ██╔██╗ ██║ ██║ ██║   ██║
  ██║╚██╗██║ ██║ ██║   ██║
  ██║ ╚████║ ██║ ╚██████╔╝
  ╚═╝  ╚═══╝ ╚═╝  ╚═════╝{R}"""

SCENE = [
    # row 0-7: title + tagline (drawn separately)
    # row 8: gap
    # row 9 onward: DB scaffold
    f"{G}  ╔═══════════════════════════════════════════════════╗{R}",
    f"{G}  ║{R} {W}~/.nio/nio.db{R}                        {D}SQLite+WAL{R} {G}║{R}",
    f"{G}  ╠═══════════════════════════════════════════════════╣{R}",
    f"{G}  ║{R}  {D}┌──────────┐  ┌────────────┐  ┌────────────┐{R} {G}║{R}",
    f"{G}  ║{R}  {D}│{W}team_state{D}│  │{W}voice_versns{D}│  │{W} schema_info{D}│{R} {G}║{R}",
    f"{G}  ║{R}  {D}└──────────┘  └────────────┘  └────────────┘{R} {G}║{R}",
    f"{G}  ║{B}══════════════════════════════════════════════════{G}║{R}",
    f"{G}  ║{R}  {D}┌──────────┐  ┌────────────┐  ┌────────────┐{R} {G}║{R}",
    f"{G}  ║{R}  {D}│{W} sessions {D}│  │{W}    turns   {D}│  │{W}soul_version{D}│{R} {G}║{R}",
    f"{G}  ║{R}  {D}└──────────┘  └────────────┘  └────────────┘{R} {G}║{R}",
    f"{G}  ║{B}══════════════════════════════════════════════════{G}║{R}",
    f"{G}  ║{R}  {D}slop_score    latency_ms       body_sha256{R}  {G}║{R}",
    f"{G}  ║{R}  {D}user_msg      slop_violations  frontmatter{R}  {G}║{R}",
    f"{G}  ║{B}══════════════════════════════════════════════════{G}║{R}",
    f"{G}  ╚═══════════════════════════════════════════════════╝{R}",
]

# Zigzag climb: alternates left/right like DK (row, col)
CLIMB_STOPS = [
    (23, 5),   # bottom-left: below scaffold
    (20, 5),   # climb up left side
    (20, 28),  # run across bottom platform to center
    (20, 52),  # run across to right side
    (16, 52),  # climb up right side
    (16, 28),  # run across middle platform to center
    (16, 5),   # run across to left side
    (12, 5),   # climb up left side
    (12, 28),  # run across top platform to center
    (12, 52),  # run across to right side
    (9, 52),   # climb to header
]


def boot_animated():
    """Run the animated boot in terminal."""
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
        # --- Title (instant) ---
        sys.stdout.write(f"\033[1;1H{TITLE}")
        _at(7, 3, f"{D}voice DNA. semver souls. anti-slop.{R}")
        _at(8, 3, f"{D}the layer hermes never had.{R}")
        sys.stdout.flush()
        time.sleep(0.4)

        # --- DB scaffold draws in fast ---
        for i, line in enumerate(SCENE):
            _at(9 + i, 1, line)
            sys.stdout.flush()
            time.sleep(0.03)

        time.sleep(0.15)

        # --- Sprite zigzags up through scaffold ---
        prev_row, prev_col = None, None
        for stop_row, stop_col in CLIMB_STOPS:
            # Erase previous sprite
            if prev_row is not None:
                for j in range(3):
                    _at(prev_row + j, prev_col, "   ")

            if prev_row is not None and stop_row == prev_row:
                # Horizontal run: slide across platform
                step = 3 if stop_col > prev_col else -3
                c = prev_col
                while (step > 0 and c < stop_col) or (step < 0 and c > stop_col):
                    for j in range(3):
                        _at(prev_row + j, c, "   ")
                    c += step
                    c = min(c, stop_col) if step > 0 else max(c, stop_col)
                    for j, sline in enumerate(SPRITE):
                        _at(stop_row + j, c, sline)
                    sys.stdout.flush()
                    time.sleep(0.025)
                # Clean up last intermediate position
                if c != stop_col:
                    for j in range(3):
                        _at(stop_row + j, c, "   ")
            elif prev_row is not None:
                # Vertical climb: draw ladder
                lo, hi = min(stop_row + 3, prev_row), max(stop_row + 3, prev_row)
                for lr in range(hi - 1, lo - 1, -1):
                    _at(lr, stop_col, f"{D}╎{R}")
                    sys.stdout.flush()
                    time.sleep(0.015)

            # Draw sprite at final position
            for j, sline in enumerate(SPRITE):
                _at(stop_row + j, stop_col, sline)

            prev_row, prev_col = stop_row, stop_col
            sys.stdout.flush()
            time.sleep(0.08)

        time.sleep(0.1)

        # --- Context drops from top ---
        drops = [
            (8, 4, f"{B}◆{G}soul{R}"),
            (8, 16, f"{B}◆{G}voice{R}"),
            (8, 29, f"{B}◆{G}memory{R}"),
            (8, 43, f"{B}◆{G}slop{R}"),
        ]
        for dr, dc, dlabel in drops:
            _at(dr, dc, dlabel)
            sys.stdout.flush()
            time.sleep(0.08)

        time.sleep(0.2)

        # --- Move cursor below scene ---
        _at(25, 1, "")
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
