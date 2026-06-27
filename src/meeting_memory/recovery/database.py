"""Physical SQLite database backup and restore."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..exceptions import BackupError
from .models import RecoveryReport, file_checksum, validate_database


@dataclass(frozen=True)
class BackupManifest:
    """Metadata describing a completed database backup."""

    source: str
    backup_path: str
    checksum: str
    size_bytes: int
    created_at: str
    schema_version: int
    meetings: int
    memories: int

    def to_dict(self) -> dict[str, object]:
        """Serialise the manifest into JSON-compatible primitives."""
        return {
            "source": self.source,
            "backup_path": self.backup_path,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "meetings": self.meetings,
            "memories": self.memories,
        }


class BackupManager:
    """Create and restore byte-for-byte SQLite backups via the online API."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    def backup(self, destination: str | Path, *, now: datetime | None = None) -> BackupManifest:
        """Back up the database to ``destination`` and return a manifest."""
        if not self.db.exists():
            raise BackupError(f"database does not exist: {self.db}")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)

        source = sqlite3.connect(self.db)
        try:
            dest = sqlite3.connect(target)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()

        report = validate_database(target)
        moment = now or datetime.now(timezone.utc)
        return BackupManifest(
            source=str(self.db),
            backup_path=str(target),
            checksum=file_checksum(target),
            size_bytes=target.stat().st_size,
            created_at=moment.isoformat(),
            schema_version=report.schema_version,
            meetings=report.meetings,
            memories=report.memories,
        )

    def restore(self, backup_path: str | Path, *, verify: bool = True) -> RecoveryReport:
        """Restore the database from ``backup_path`` (validated by default)."""
        source_path = Path(backup_path)
        if not source_path.exists():
            raise BackupError(f"backup does not exist: {source_path}")
        if verify:
            report = validate_database(source_path)
            if not report.ok:
                raise BackupError(
                    f"refusing to restore corrupt backup {source_path} "
                    f"(integrity={report.integrity})"
                )

        self.db.parent.mkdir(parents=True, exist_ok=True)
        # Replace the destination outright so recovery works even when the live
        # database is corrupt (online backup cannot write into a broken file).
        for suffix in ("", "-wal", "-shm"):
            stale = Path(f"{self.db}{suffix}")
            if stale.exists():
                stale.unlink()
        source = sqlite3.connect(source_path)
        try:
            dest = sqlite3.connect(self.db)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()
        return validate_database(self.db)
