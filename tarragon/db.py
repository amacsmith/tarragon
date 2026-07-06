"""Database configuration and utilities."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Any

DB_PATH = Path(__file__).parent.parent / "tarragon.db"


def get_db_path() -> Path:
    """Get the database path."""
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    schema = """
    -- Accounts table
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        makerworld_token TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    -- Collections table
    CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        external_id TEXT NOT NULL UNIQUE,
        FOREIGN KEY (account_id) REFERENCES accounts(id)
    );

    -- Models table
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collection_id INTEGER NOT NULL,
        external_id TEXT NOT NULL,
        name TEXT NOT NULL,
        thumbnail_url TEXT,
        mesh_file_path TEXT,
        FOREIGN KEY (collection_id) REFERENCES collections(id),
        UNIQUE(collection_id, external_id)
    );

    -- SCAD jobs table
    CREATE TABLE IF NOT EXISTS scad_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        scad_code TEXT,
        params_json TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (model_id) REFERENCES models(id)
    );
    """
    
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for statement in schema.strip().split(';'):
            if statement.strip():
                cursor.execute(statement)
        # Migration: accounts.handle (added for real MakerWorld sync)
        cols = {row["name"] for row in cursor.execute("PRAGMA table_info(accounts)")}
        if "handle" not in cols:
            cursor.execute("ALTER TABLE accounts ADD COLUMN handle TEXT")
        conn.commit()


if __name__ == "__main__":
    init_db()
