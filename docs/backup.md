# Backup & recovery

Two complementary mechanisms protect stored organizational memory. Both verify
integrity and checksums before restoring, so corrupt data is never silently
recovered.

| Mechanism | Format | Use it for |
| --- | --- | --- |
| **Physical backup** | byte-for-byte SQLite copy | Fast, exact backups/restores. |
| **Logical snapshot** | portable, checksummed JSON | Schema-version migration, inspection, transport. |

## Physical backup & restore

Uses the SQLite online backup API, so it is safe on a live database.

```bash
meeting-memory backup  --db atlas.db -o atlas.bak
meeting-memory restore --db restored.db atlas.bak
meeting-memory restore --db restored.db atlas.bak --no-verify   # skip validation
```

```python
from meeting_memory.recovery import BackupManager

manifest = BackupManager("atlas.db").backup("atlas.bak")
print(manifest.checksum, manifest.meetings, manifest.memories)

report = BackupManager("restored.db").restore("atlas.bak")
print(report.ok, report.integrity, report.meetings)
```

Restore **replaces** the destination (including any `-wal`/`-shm` sidecars), so
it recovers correctly even when the live database is corrupt. By default it
refuses to restore a backup that fails validation.

## Logical snapshots

A snapshot exports every meeting and memory as JSON with a content checksum.

```bash
meeting-memory backup  --db atlas.db -o atlas.snapshot.json --snapshot
meeting-memory restore --db rebuilt.db atlas.snapshot.json --snapshot
```

```python
from meeting_memory.recovery import export_snapshot, import_snapshot, verify_snapshot

snapshot = export_snapshot("atlas.db", "atlas.snapshot.json")
assert verify_snapshot(snapshot)                      # recompute + compare checksum
report = import_snapshot("atlas.snapshot.json", "rebuilt.db")
print(report.ok, report.meetings, report.memories)
```

Import rebuilds the database from scratch, inserting meetings first and memories
in two passes so the self-referential `superseded_by` foreign key is always
satisfied. It refuses to import a snapshot whose checksum does not match (unless
`verify=False`).

## Validation & checksums

```python
from meeting_memory.recovery import validate_database, file_checksum

report = validate_database("atlas.db")   # runs PRAGMA integrity_check + row counts
print(report.ok, report.integrity, report.schema_version)

digest = file_checksum("atlas.bak")      # streaming SHA-256
```

`RecoveryReport` reports `ok`, `integrity`, `schema_version`, `meetings`,
`memories`, and any `messages` (for example, missing tables).

## Recommended routine

1. Take a physical backup on a schedule (`meeting-memory backup`).
2. Periodically export a logical snapshot for portability and inspection.
3. Validate backups with `validate_database` before relying on them.
4. To recover, `restore` from the most recent valid backup; the target database
   is replaced atomically.
