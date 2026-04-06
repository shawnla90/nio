"""SQLite database: schema, migrations, connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

NIO_HOME = Path.home() / ".nio"
DB_PATH = NIO_HOME / "nio.db"

SCHEMA_VERSION = 1

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS soul_versions (
    soul_id     TEXT NOT NULL,
    version     TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    body        TEXT NOT NULL,
    frontmatter JSON NOT NULL,
    released_at TIMESTAMP NOT NULL,
    released_by TEXT,
    changelog   TEXT,
    PRIMARY KEY (soul_id, version)
);

CREATE TABLE IF NOT EXISTS voice_versions (
    voice_id    TEXT NOT NULL,
    version     TEXT NOT NULL,
    body        TEXT NOT NULL,
    rules       JSON NOT NULL,
    released_at TIMESTAMP NOT NULL,
    PRIMARY KEY (voice_id, version)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    started_at    TIMESTAMP NOT NULL,
    ended_at      TIMESTAMP,
    soul_id       TEXT,
    soul_version  TEXT,
    voice_id      TEXT,
    voice_version TEXT,
    platform      TEXT,
    team_id       TEXT,
    task_type     TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    turn_id         TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id),
    turn_index      INTEGER NOT NULL,
    user_msg        TEXT,
    agent_msg       TEXT,
    latency_ms      INTEGER,
    slop_score      REAL,
    slop_violations JSON,
    tool_calls      JSON,
    memory_hits     INTEGER DEFAULT 0,
    user_signal     INTEGER,
    created_at      TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS team_state (
    team_id      TEXT PRIMARY KEY,
    origin_url   TEXT,
    soul_id      TEXT,
    soul_version TEXT,
    manifest     JSON NOT NULL,
    last_sync_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_created ON turns(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_soul ON sessions(soul_id, soul_version);

CREATE TABLE IF NOT EXISTS schema_info (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database with the current schema."""
    conn = get_connection()
    conn.executescript(SCHEMA_V1)

    # Record schema version
    conn.execute(
        "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()
    conn.close()


def check_db() -> bool:
    """Check if the database exists and has the correct schema."""
    if not DB_PATH.exists():
        return False
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT value FROM schema_info WHERE key = 'schema_version'"
        ).fetchone()
        conn.close()
        return row is not None and int(row[0]) >= SCHEMA_VERSION
    except Exception:
        return False


def get_schema_version() -> int:
    """Get the current schema version from the database."""
    if not DB_PATH.exists():
        return 0
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT value FROM schema_info WHERE key = 'schema_version'"
        ).fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except Exception:
        return 0
