"""NIO terminal boot sequence.

Donkey Kong-style: boss throws 429 rate limits, NIO dodges and climbs.
Sprite zigzags platforms, jumps over barrels, knocks boss off, victory.
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
SPRITE_JUMP = [f"{YEL}▄█▄{R}", f"{YEL}▐█▌{R}", f"{YEL}▀ ▀{R}"]  # dodge flash

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

SCN = 9  # scene start row

# Zigzag climb path: (row, col)
CLIMB = [
    (SCN + 13, 5),                       # start bottom-left
    (SCN + 13, 28), (SCN + 13, 50),      # run right across bottom
    (SCN + 10, 50),                       # climb right side
    (SCN + 10, 28), (SCN + 10, 5),       # run left across middle
    (SCN + 6, 5),                         # climb left side
    (SCN + 6, 28), (SCN + 6, 50),        # run right across upper
    (SCN + 2, 50),                        # climb to top-right (AWAY from boss at col 25)
]

# Barrel drops: (barrel_col, trigger_step, dodge_col)
# dodge_col = where sprite jumps to dodge (opposite side of barrel)
BARRELS = [
    (48, 1, 10),    # barrel right, sprite dodges left
    (8, 3, 50),     # barrel left, sprite is already right
    (48, 5, 10),    # barrel right, sprite dodges left
    (8, 6, 50),     # barrel left BEFORE sprite reaches center (was step 7)
    (28, 9, 50),    # barrel center on final climb, sprite is right
]


def _draw_sprite(row, col):
    for j, s in enumerate(SPRITE):
        _at(row + j, col, s)


def _draw_sprite_jump(row, col):
    """Flash sprite in yellow (dodge state)."""
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
    """Animate a 429 barrel falling down fast."""
    for r in range(start_row, end_row + 1, 2):
        if r > start_row:
            _at(r - 2, col, BARREL_CLEAR)
        _at(r, col, BARREL)
        sys.stdout.flush()
        time.sleep(0.02)
    _at(end_row, col, BARREL_CLEAR)
    sys.stdout.flush()


def _dodge_jump(row, from_col, to_col):
    """Sprite jumps sideways to dodge a barrel (quick hop)."""
    _clear_sprite(row, from_col)
    # Jump up 1 row briefly
    _draw_sprite_jump(row - 1, to_col)
    sys.stdout.flush()
    time.sleep(0.06)
    _clear_sprite(row - 1, to_col)
    # Land at dodge position
    _draw_sprite(row, to_col)
    sys.stdout.flush()
    time.sleep(0.04)


def _slide(from_col, to_col, row):
    """Slide sprite horizontally."""
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


def _climb_vertical(from_row, to_row, col):
    """Climb sprite vertically."""
    direction = -1 if to_row < from_row else 1
    r = from_row
    while r != to_row:
        _clear_sprite(r, col)
        r += direction
        _at(r + (2 if direction == -1 else 0), col + 1, f"{D}╎{R}")
        _draw_sprite(r, col)
        sys.stdout.flush()
        time.sleep(0.02)


def _get_memory_stats():
    """Query nio.db for session/turn counts (returns defaults if no DB)."""
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

        # --- Boss appears at top-left of scaffold ---
        boss_row, boss_col = SCN, 5
        _draw_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.25)

        # Boss shakes
        for _ in range(2):
            _draw_boss(boss_row, boss_col + 1)
            sys.stdout.flush()
            time.sleep(0.05)
            _draw_boss(boss_row, boss_col - 1)
            sys.stdout.flush()
            time.sleep(0.05)
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

            # Check if boss should throw a barrel
            if barrel_idx < len(BARRELS):
                bcol, btrigger, dodge_col = BARRELS[barrel_idx]
                if step_i == btrigger:
                    # Boss shakes and throws
                    _draw_boss(boss_row, boss_col + 1)
                    sys.stdout.flush()
                    time.sleep(0.03)
                    _draw_boss(boss_row, boss_col)

                    # Sprite dodges if barrel lands near current position
                    sprite_near_barrel = abs(prev_col - bcol) < 10
                    if sprite_near_barrel:
                        _dodge_jump(prev_row, prev_col, dodge_col)
                        prev_col = dodge_col

                    # Barrel falls
                    _drop_barrel(bcol, SCN + 1, SCN + 13)
                    barrel_idx += 1

            # Move sprite to next stop
            if stop_row == prev_row:
                _slide(prev_col, stop_col, stop_row)
            else:
                _climb_vertical(prev_row, stop_row, prev_col)
                if stop_col != prev_col:
                    prev_row = stop_row
                    _slide(prev_col, stop_col, stop_row)

            prev_row, prev_col = stop_row, stop_col

        time.sleep(0.1)

        # --- NIO charges boss from the right ---
        # Sprite is at (SCN+2, 50), boss is at (SCN, 5)
        # Sprite dashes left toward boss
        _at(prev_row, prev_col + 4, f"{B}>{R}")  # charge indicator
        sys.stdout.flush()
        time.sleep(0.08)
        _at(prev_row, prev_col + 4, " ")

        # Quick slide toward boss (stop at col 14, not overlapping boss at col 5)
        _slide(prev_col, 14, prev_row)
        prev_col = 14
        sys.stdout.flush()
        time.sleep(0.05)

        # Impact flash
        _draw_sprite_jump(prev_row, prev_col)
        sys.stdout.flush()
        time.sleep(0.06)
        _draw_sprite(prev_row, prev_col)

        # Boss gets hit - flashes and tumbles off LEFT side
        _clear_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.05)
        _draw_boss(boss_row, boss_col)
        sys.stdout.flush()
        time.sleep(0.05)

        # Boss falls off left
        for offset in range(1, 6):
            _clear_boss(boss_row + offset - 1, boss_col - (offset - 1) * 2)
            new_r = boss_row + offset
            new_c = max(1, boss_col - offset * 2)
            if new_r < SCN + 15:
                _draw_boss(new_r, new_c)
            sys.stdout.flush()
            time.sleep(0.04)

        # Clear last boss position
        _clear_boss(boss_row + 5, max(1, boss_col - 10))
        sys.stdout.flush()

        time.sleep(0.15)

        # --- Victory moment ---
        # Move sprite to center of top platform
        _slide(prev_col, 28, prev_row)

        # Victory text
        _at(8, 12, f"{BOLD}{B}  ETERNAL MEMORY LOADED  {R}")
        sys.stdout.flush()
        time.sleep(0.3)

        # Context items drop in
        drops = [
            (SCN - 2, 5, f"{B}◆{G} soul{R}"),
            (SCN - 2, 17, f"{B}◆{G} voice{R}"),
            (SCN - 2, 30, f"{B}◆{G} memory{R}"),
            (SCN - 2, 44, f"{B}◆{G} anti-slop{R}"),
        ]
        for dr, dc, dlabel in drops:
            _at(dr, dc, dlabel)
            sys.stdout.flush()
            time.sleep(0.08)

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
    print(f"  {D}voice DNA. semver souls. anti-slop.{R}")
    print(f"  {D}the layer hermes never had.{R}")
    print()
    for line in SCENE:
        print(line)
    sessions, turns = _get_memory_stats()
    if sessions > 0:
        print(f"  {D}sessions: {W}{sessions}{D}  turns: {W}{turns}{D}  memory: {B}eternal{R}")
    else:
        print(f"  {D}first run. memory starts now.{R}")
    print()
