#!/usr/bin/env python
"""Demonstrate backup, restore, and snapshot recovery.

Builds a temporary database, makes a physical backup and a logical snapshot,
restores both into fresh databases, and verifies the row counts match. Entirely
self-contained and deterministic.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from meeting_memory.benchmarks import get_preset, write_dataset
from meeting_memory.recovery import (
    BackupManager,
    export_snapshot,
    import_snapshot,
    validate_database,
    verify_snapshot,
)
from meeting_memory.services import MeetingService


def main() -> int:
    """Run a full backup/restore and snapshot/import round trip."""
    with TemporaryDirectory(prefix="mm-backup-") as tmp:
        root = Path(tmp)
        data_dir = root / "data"
        write_dataset(get_preset("small"), data_dir)
        db = root / "primary.db"
        MeetingService(db).import_path(data_dir, recursive=True)

        # Physical backup + restore.
        backup_path = root / "primary.bak"
        manifest = BackupManager(db).backup(backup_path)
        print(f"Backup checksum: {manifest.checksum}")
        restored = BackupManager(root / "restored.db").restore(backup_path)
        print(f"Restored backup: ok={restored.ok} memories={restored.memories}")

        # Logical snapshot + import.
        snapshot_path = root / "primary.snapshot.json"
        snapshot = export_snapshot(db, snapshot_path)
        print(f"Snapshot verified: {verify_snapshot(snapshot)}")
        imported = import_snapshot(snapshot_path, root / "from_snapshot.db")
        print(f"Imported snapshot: ok={imported.ok} memories={imported.memories}")

        original = validate_database(db)
        assert original.memories == restored.memories == imported.memories
        print("All recovery paths produced matching row counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
