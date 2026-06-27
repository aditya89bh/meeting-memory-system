"""Shared recovery types, checksums, and database validation."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ..exceptions import BackupError

_CHUNK = 65536


@dataclass(frozen=True)
class RecoveryReport:
    """The outcome of validating or recovering a database."""

    ok: bool
    integrity: str
    schema_version: int
    meetings: int
    memories: int
    messages: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        """Serialise the report into JSON-compatible primitives."""
        return {
            "ok": self.ok,
            "integrity": self.integrity,
            "schema_version": self.schema_version,
            "meetings": self.meetings,
            "memories": self.memories,
            "messages": list(self.messages),
        }


def file_checksum(path: str | Path, *, algorithm: str = "sha256") -> str:
    """Return the hex digest of a file, read in chunks for large databases."""
    digest = hashlib.new(algorithm)
    file_path = Path(path)
    if not file_path.exists():
        raise BackupError(f"cannot checksum missing file: {file_path}")
    with file_path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def validate_database(path: str | Path) -> RecoveryReport:
    """Run ``PRAGMA integrity_check`` and count rows in a database file."""
    file_path = Path(path)
    if not file_path.exists():
        raise BackupError(f"database does not exist: {file_path}")

    messages: list[str] = []
    connection = sqlite3.connect(file_path)
    try:
        integrity_row = connection.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "unknown"
        schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        meetings = _safe_count(connection, "meetings", messages)
        memories = _safe_count(connection, "memories", messages)
    finally:
        connection.close()

    ok = integrity == "ok" and not messages
    return RecoveryReport(
        ok=ok,
        integrity=integrity,
        schema_version=schema_version,
        meetings=meetings,
        memories=memories,
        messages=tuple(messages),
    )


def _safe_count(connection: sqlite3.Connection, table: str, messages: list[str]) -> int:
    """Count rows in ``table``, recording a message if the table is missing."""
    try:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    except sqlite3.OperationalError as exc:
        messages.append(f"missing table {table!r}: {exc}")
        return 0
    return int(row[0])
