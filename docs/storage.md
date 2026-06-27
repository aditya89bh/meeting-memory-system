# Persistent meeting memory (Phase 3)

Phase 3 adds a durable storage layer that turns one-off extraction into
organizational memory accumulated across many meetings. It is deterministic and
dependency-free: standard-library `sqlite3` only — **no ORM, no vector database,
and no semantic search**.

The store answers questions such as:

- What decisions have we made?
- What commitments are still open?
- Which risks keep appearing?
- When did this assumption first appear?
- Which meetings discussed Project X?

## Architecture

```
file ──▶ load ──▶ parse ──▶ extract ──▶ persist ──▶ SQLite database
                                            │
                                            ├── meetings   (registry)
                                            ├── memories   (one per primitive)
                                            ├── evidence   (source spans)
                                            └── metadata   (key/value extras)
```

The layer lives under `src/meeting_memory/storage/`:

| Module           | Responsibility                                                   |
| ---------------- | --------------------------------------------------------------- |
| `models.py`      | `StoredMeeting`, `StoredMemory`, `StoredEvidence`, `MemoryStatus`, `MemoryQuery` |
| `hashing.py`     | Deterministic transcript and memory content hashes              |
| `migrations.py`  | Ordered, append-only schema migrations + `apply_migrations`     |
| `base.py`        | `MemoryStore` abstraction (CRUD, registry, query helpers, lifecycle) |
| `sqlite_store.py`| `SQLiteMemoryStore` — the concrete `sqlite3` implementation     |
| `persistence.py` | `persist_extraction` — bridge from `ExtractionResult` to rows   |
| `dedup.py`       | Memory-level duplicate detection                                |
| `importer.py`    | `import_meeting` — the end-to-end load/parse/extract/persist pipeline |

### Design principles

- **Deterministic.** Hashes are plain SHA-256 over normalized text; all reads use
  explicit, stable `ORDER BY` clauses (with `memory_id` as a tiebreaker).
- **No ORM.** Rows are mapped to/from frozen dataclasses by hand, keeping the SQL
  explicit and auditable.
- **Immutable records.** `StoredMeeting` and `StoredMemory` are frozen dataclasses.
- **Specific errors.** Storage failures raise subclasses of `StorageError`
  (`MemoryNotFoundError`, `MeetingNotFoundError`, `DuplicateMeetingError`).

## Schema

The database is a single SQLite file. Its version is tracked with
`PRAGMA user_version`; foreign keys are enabled on every connection.

```sql
CREATE TABLE meetings (
    meeting_id       TEXT PRIMARY KEY,
    title            TEXT,
    date             TEXT,
    source           TEXT,
    duration_seconds REAL,
    participants     TEXT NOT NULL DEFAULT '[]',   -- JSON array
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
    owner_type TEXT NOT NULL,    -- 'memory' (extensible to 'meeting', ...)
    owner_id   TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL
);
```

Indexes back the common access paths: `meetings(date)`, `memories(meeting_id)`,
`memories(memory_type)`, `memories(status)`, `memories(speaker)`,
`memories(content_hash)`, `evidence(memory_id)`, and `metadata(owner_type, owner_id)`.

The `superseded_by`, `content_hash`, and generic `metadata` columns are present
from version 1 so lifecycle and duplicate-detection features need no later schema
change.

## Migration strategy

`migrations.py` holds an ordered, append-only tuple of SQL scripts. The index of
a script is the version it upgrades **to**:

```python
MIGRATIONS = (_MIGRATION_001,)   # index 0 -> user_version 1
```

`apply_migrations(connection)` reads the current `user_version` and runs every
script after it, bumping the version as it goes. Opening an existing database
applies only the missing migrations; opening a current one is a no-op. **To
evolve the schema, append a new script — never edit an existing one.**

## Import pipeline

```python
from meeting_memory.storage import SQLiteMemoryStore, import_meeting

with SQLiteMemoryStore("atlas.db") as store:
    result = import_meeting("examples/history/meeting1.txt", store)
    print("\n".join(result.summary_lines()))
```

`import_meeting` reads the raw transcript, hashes it, and short-circuits to a
duplicate result if that hash (or the derived meeting id) is already stored.
Otherwise it parses, extracts, and persists the meeting and its memories, then
returns an `ImportResult` with per-type counts and the number of skipped
duplicates.

## Query interface

`MemoryStore` provides convenience finders plus a general `query`:

```python
store.find_by_type("decision", "commitment")
store.find_by_speaker("Alice")
store.find_by_meeting("meeting1")
store.find_by_confidence(0.8, 0.95)
store.find_by_date("2026-02-02")
store.find_between_dates("2026-02-01", "2026-02-28")
store.find_active()
store.find_by_status(MemoryStatus.ARCHIVED)
```

For arbitrary combinations build a `MemoryQuery`; populated filters AND-combine,
date filters compare against the owning meeting's date, and results are ordered
deterministically:

```python
from meeting_memory.storage import MemoryQuery, MemoryStatus

store.query(MemoryQuery(
    memory_types=frozenset({"risk"}),
    statuses=frozenset({MemoryStatus.ACTIVE}),
    date_from="2026-02-01",
    order_by="confidence",
    descending=True,
    limit=10,
))
```

## Lifecycle

Memories start `ACTIVE` and transition with explicit methods:

| Method                         | Resulting status | Notes                              |
| ------------------------------ | ---------------- | ---------------------------------- |
| `archive(id)`                  | `ARCHIVED`       | No longer current, kept for history|
| `resolve(id)`                  | `RESOLVED`       | A commitment/open loop was closed  |
| `supersede(id, by_id)`         | `SUPERSEDED`     | Records `superseded_by`            |
| `mark_deleted(id)`             | `DELETED`        | Soft delete (row retained)         |
| `restore(id)`                  | `ACTIVE`         | Bring a memory back                 |

Every transition updates `updated_at`. `delete(id)` (as opposed to
`mark_deleted`) hard-removes the row and its evidence/metadata.

## Duplicate detection

- **Meeting level:** `transcript_hash` is `UNIQUE`; the importer checks it before
  doing any work, so re-importing the same transcript is a deterministic no-op.
- **Memory level:** during persistence, a candidate is skipped if it shares a
  `content_hash` (memory type + normalized text) with an existing memory in the
  same meeting within a confidence threshold. The same point can still recur in
  *different* meetings — that recurrence is the signal behind "which risks keep
  appearing?".

## Future extensions

- Additional back-ends behind the `MemoryStore` abstraction (e.g. Postgres).
- Cross-meeting linking of recurring memories via their shared `content_hash`.
- Storing meeting-level extras in the generic `metadata` table (`owner_type`
  `'meeting'`) — the schema already allows it.
- An LLM-backed extractor (Phase 2 extension point) would persist through exactly
  the same storage layer with no schema changes.
