from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    language TEXT NOT NULL,
    participants TEXT NOT NULL DEFAULT '[]',
    topics TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    folder TEXT NOT NULL
);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.execute(_SCHEMA)
    connection.commit()
    return connection
