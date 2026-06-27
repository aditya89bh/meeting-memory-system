"""Backup, restore, and snapshot recovery (Phase 9).

Two complementary mechanisms keep stored organizational memory safe:

* **Physical backup** copies the SQLite database file byte-for-byte using the
  ``sqlite3`` online backup API, recording a checksum and a manifest.
* **Logical snapshots** export meetings and memories as portable, checksummed
  JSON that can be re-imported into a fresh database.

Both verify integrity on the way in and out, so recovery never silently restores
corrupt data.
"""

from __future__ import annotations

from .database import BackupManager, BackupManifest
from .models import RecoveryReport, file_checksum, validate_database
from .snapshot import Snapshot, export_snapshot, import_snapshot, verify_snapshot

__all__ = [
    "BackupManager",
    "BackupManifest",
    "RecoveryReport",
    "Snapshot",
    "export_snapshot",
    "file_checksum",
    "import_snapshot",
    "validate_database",
    "verify_snapshot",
]
