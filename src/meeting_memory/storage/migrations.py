"""Deterministic schema migrations for the SQLite memory store.

Migrations are an ordered, append-only list of SQL scripts. The database's
``PRAGMA user_version`` records how many have been applied, so opening an old
database upgrades it in place and opening a current one is a no-op. To evolve the
schema, append a new script — never edit an existing one.
"""

from __future__ import annotations

import sqlite3

# Version 1: the initial schema. Columns such as ``superseded_by`` and
# ``content_hash`` are present from the start so later lifecycle and duplicate
# detection features need no schema change.
_MIGRATION_001 = """
CREATE TABLE meetings (
    meeting_id       TEXT PRIMARY KEY,
    title            TEXT,
    date             TEXT,
    source           TEXT,
    duration_seconds REAL,
    participants     TEXT NOT NULL DEFAULT '[]',
    transcript_hash  TEXT NOT NULL UNIQUE,
    created_at       TEXT NOT NULL
);

CREATE TABLE memories (
    memory_id       TEXT PRIMARY KEY,
    meeting_id      TEXT NOT NULL REFERENCES meetings (meeting_id) ON DELETE CASCADE,
    memory_type     TEXT NOT NULL,
    speaker         TEXT,
    text            TEXT NOT NULL,
    confidence      REAL NOT NULL,
    utterance_index INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    superseded_by   TEXT REFERENCES memories (memory_id) ON DELETE SET NULL,
    content_hash    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE evidence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id       TEXT NOT NULL REFERENCES memories (memory_id) ON DELETE CASCADE,
    utterance_index INTEGER NOT NULL,
    start           INTEGER NOT NULL,
    end             INTEGER NOT NULL,
    text            TEXT NOT NULL
);

CREATE TABLE metadata (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_type TEXT NOT NULL,
    owner_id   TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL
);

CREATE INDEX idx_meetings_date ON meetings (date);
CREATE INDEX idx_memories_meeting ON memories (meeting_id);
CREATE INDEX idx_memories_type ON memories (memory_type);
CREATE INDEX idx_memories_status ON memories (status);
CREATE INDEX idx_memories_speaker ON memories (speaker);
CREATE INDEX idx_memories_content_hash ON memories (content_hash);
CREATE INDEX idx_evidence_memory ON evidence (memory_id);
CREATE INDEX idx_metadata_owner ON metadata (owner_type, owner_id);
"""

# Ordered migrations; index i upgrades the database to version i + 1.
MIGRATIONS: tuple[str, ...] = (_MIGRATION_001,)

SCHEMA_VERSION: int = len(MIGRATIONS)


def apply_migrations(connection: sqlite3.Connection) -> int:
    """Apply any pending migrations and return the resulting schema version."""
    current: int = connection.execute("PRAGMA user_version").fetchone()[0]
    for version in range(current, len(MIGRATIONS)):
        connection.executescript(MIGRATIONS[version])
        # ``user_version`` cannot be parameterised; ``version`` is a trusted int.
        connection.execute(f"PRAGMA user_version = {version + 1}")
    connection.commit()
    return len(MIGRATIONS)
