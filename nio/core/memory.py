"""Eternal memory: cross-session context persistence and Hermes memory bridge.

Sessions survive shutdown. New sessions carry context from previous ones.
Memory bridge syncs between NIO's DB and Hermes's MEMORY.md/USER.md files.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERMES_MEMORIES = Path.home() / ".hermes" / "memories"
CLAUDE_HANDOFFS = Path.home() / ".claude" / "handoffs"


def import_hermes_memories() -> int:
    """Import Hermes memory files into NIO's memory_context table.

    Reads ~/.hermes/memories/MEMORY.md and USER.md, splits on paragraph breaks,
    deduplicates by content hash, stores each as a memory_context row.
    Returns count of new rows inserted.
    """
    from nio.core.db import get_connection

    conn = get_connection()

    # Ensure table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_context (
            context_id    TEXT PRIMARY KEY,
            source        TEXT NOT NULL,
            content       TEXT NOT NULL,
            content_hash  TEXT NOT NULL,
            imported_at   TIMESTAMP NOT NULL,
            expires_at    TIMESTAMP,
            tags          JSON DEFAULT '[]'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_context(source)")

    count = 0
    for filename, source in [("MEMORY.md", "hermes_memory"), ("USER.md", "hermes_user")]:
        filepath = HERMES_MEMORIES / filename
        if not filepath.exists():
            continue

        content = filepath.read_text().strip()
        # Split on double newlines (paragraph breaks) or section markers
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and len(p.strip()) > 10]

        for para in paragraphs:
            content_hash = hashlib.sha256(para.encode()).hexdigest()

            # Skip if already imported
            existing = conn.execute(
                "SELECT 1 FROM memory_context WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if existing:
                continue

            conn.execute(
                """INSERT INTO memory_context (context_id, source, content, content_hash, imported_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), source, para, content_hash, datetime.now(timezone.utc).isoformat()),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def import_claude_handoffs() -> int:
    """Import Claude Code handoff files into NIO's memory_context table.

    Scans ~/.claude/handoffs/*.md, parses sections, stores as memory_context
    with source='claude_handoff'. Deduplicates by content hash.
    Returns count of new rows inserted.
    """
    import re

    from nio.core.db import get_connection

    if not CLAUDE_HANDOFFS.is_dir():
        return 0

    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_context (
            context_id    TEXT PRIMARY KEY,
            source        TEXT NOT NULL,
            content       TEXT NOT NULL,
            content_hash  TEXT NOT NULL,
            imported_at   TIMESTAMP NOT NULL,
            expires_at    TIMESTAMP,
            tags          JSON DEFAULT '[]'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_context(source)")

    count = 0
    for md_file in sorted(CLAUDE_HANDOFFS.glob("*.md")):
        if md_file.name.endswith("_done.md"):
            continue

        content = md_file.read_text().strip()
        if not content:
            continue

        # Parse sections from handoff markdown
        sections = re.split(r'\n## ', content)
        for section in sections:
            section = section.strip()
            if len(section) < 20:
                continue

            content_hash = hashlib.sha256(section.encode()).hexdigest()
            existing = conn.execute(
                "SELECT 1 FROM memory_context WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            if existing:
                continue

            # Extract section title for tags
            title = section.split("\n")[0].strip("# ").strip()
            tags = json.dumps(["handoff", title[:50]] if title else ["handoff"])

            conn.execute(
                """INSERT INTO memory_context
                   (context_id, source, content, content_hash, imported_at, tags)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), "claude_handoff", section[:2000],
                 content_hash, datetime.now(timezone.utc).isoformat(), tags),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def get_session_context(last_n: int = 3) -> dict:
    """Build context from recent sessions and memory facts.

    Returns:
        {
            "last_session_summary": str,
            "memory_facts": list[str],
            "session_count": int,
            "turn_count": int,
        }
    """
    from nio.core.db import get_connection

    conn = get_connection()

    # Total counts
    session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] or 0
    turn_count = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0] or 0

    # Last N session summaries
    sessions = conn.execute(
        """SELECT session_id, soul_id, soul_version, task_type, started_at
           FROM sessions WHERE ended_at IS NOT NULL
           ORDER BY ended_at DESC LIMIT ?""",
        (last_n,),
    ).fetchall()

    last_summary = ""
    if sessions:
        sid = sessions[0][0]
        last_summary = summarize_session(sid, conn=conn)

    # Memory facts from memory_context
    memory_facts = []
    try:
        rows = conn.execute(
            "SELECT content FROM memory_context ORDER BY imported_at DESC LIMIT 10"
        ).fetchall()
        memory_facts = [r[0][:200] for r in rows]
    except Exception:
        pass  # Table might not exist yet

    conn.close()

    return {
        "last_session_summary": last_summary,
        "memory_facts": memory_facts,
        "session_count": session_count,
        "turn_count": turn_count,
    }


def summarize_session(session_id: str, conn=None) -> str:
    """Generate a 2-3 sentence summary of a session from its turns."""
    from nio.core.db import get_connection

    should_close = conn is None
    if conn is None:
        conn = get_connection()

    # Get session metadata
    session = conn.execute(
        "SELECT soul_id, task_type, started_at FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    if not session:
        if should_close:
            conn.close()
        return ""

    soul_id, task_type, started_at = session

    # Get first user message and last agent message
    first_user = conn.execute(
        "SELECT user_msg FROM turns WHERE session_id = ? AND user_msg != '' ORDER BY turn_index LIMIT 1",
        (session_id,),
    ).fetchone()

    turn_count = conn.execute(
        "SELECT COUNT(*) FROM turns WHERE session_id = ?", (session_id,)
    ).fetchone()[0]

    slop_avg = conn.execute(
        "SELECT AVG(slop_score) FROM turns WHERE session_id = ? AND slop_score IS NOT NULL",
        (session_id,),
    ).fetchone()[0]

    if should_close:
        conn.close()

    # Build summary
    parts = []
    if task_type and task_type != "general":
        parts.append(f"Task: {task_type}")
    if soul_id:
        parts.append(f"soul: {soul_id}")
    parts.append(f"{turn_count} turns")
    if slop_avg is not None:
        parts.append(f"slop avg: {slop_avg:.0f}")

    summary = ", ".join(parts) + "."

    if first_user and first_user[0]:
        user_preview = first_user[0][:100]
        summary += f" Started with: {user_preview}"

    return summary


def sync_back_to_hermes(context: dict):
    """Write key NIO context back to ~/.hermes/memories/MEMORY.md.

    Appends a section marker so Hermes sessions benefit from NIO's accumulated context.
    """
    memory_file = HERMES_MEMORIES / "MEMORY.md"
    if not memory_file.parent.exists():
        return

    nio_section = f"""

## NIO Context (auto-synced)
Sessions: {context.get('session_count', 0)}
Turns: {context.get('turn_count', 0)}
Last session: {context.get('last_session_summary', 'none')}
"""

    if memory_file.exists():
        current = memory_file.read_text()
        # Replace existing NIO section if present
        if "## NIO Context (auto-synced)" in current:
            parts = current.split("## NIO Context (auto-synced)")
            # Find end of NIO section (next ## or end of file)
            if len(parts) > 1:
                rest = parts[1]
                next_section = rest.find("\n## ")
                if next_section >= 0:
                    after = rest[next_section:]
                else:
                    after = ""
                current = parts[0].rstrip() + nio_section + after
            else:
                current = current.rstrip() + nio_section
        else:
            current = current.rstrip() + nio_section
        memory_file.write_text(current)
    else:
        memory_file.write_text(nio_section.strip() + "\n")
