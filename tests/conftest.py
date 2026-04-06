"""Shared test fixtures for NIO test suite."""

import sqlite3

import pytest


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary NIO database for testing.

    Patches get_connection to use a temp SQLite file.
    Runs init_db to create all schema tables.
    """
    db_path = tmp_path / "nio.db"

    import nio.core.db as db_mod

    def patched_get_connection():
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    monkeypatch.setattr(db_mod, "get_connection", patched_get_connection)
    db_mod.init_db()
    return db_path
