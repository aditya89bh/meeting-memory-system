"""Portable, checksummed logical snapshots of stored memory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from ..exceptions import BackupError
from ..storage import (
    MemoryStatus,
    SQLiteMemoryStore,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
)
from .models import RecoveryReport, validate_database

SNAPSHOT_VERSION = 1


@dataclass(frozen=True)
class Snapshot:
    """A portable export of every meeting and memory in a database."""

    version: int
    schema_version: int
    created_at: str
    meetings: tuple[dict[str, object], ...]
    memories: tuple[dict[str, object], ...]
    checksum: str

    def to_dict(self) -> dict[str, object]:
        """Serialise the snapshot into JSON-compatible primitives."""
        return {
            "version": self.version,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "checksum": self.checksum,
            "meetings": [dict(meeting) for meeting in self.meetings],
            "memories": [dict(memory) for memory in self.memories],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the snapshot to JSON text."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Snapshot:
        """Reconstruct a snapshot from a parsed JSON object."""
        try:
            meetings = tuple(cast("list[dict[str, object]]", data["meetings"]))
            memories = tuple(cast("list[dict[str, object]]", data["memories"]))
            return cls(
                version=int(cast("int", data["version"])),
                schema_version=int(cast("int", data["schema_version"])),
                created_at=str(data["created_at"]),
                meetings=meetings,
                memories=memories,
                checksum=str(data["checksum"]),
            )
        except KeyError as exc:
            raise BackupError(f"snapshot is missing required field: {exc}") from exc


def _payload_checksum(
    meetings: tuple[dict[str, object], ...], memories: tuple[dict[str, object], ...]
) -> str:
    """Return a stable checksum over the snapshot's logical contents."""
    payload = json.dumps(
        {"meetings": list(meetings), "memories": list(memories)},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def export_snapshot(
    db: str | Path,
    destination: str | Path | None = None,
    *,
    now: datetime | None = None,
) -> Snapshot:
    """Export every meeting and memory from ``db`` into a checksummed snapshot."""
    db_path = Path(db)
    if not db_path.exists():
        raise BackupError(f"database does not exist: {db_path}")

    with SQLiteMemoryStore(db_path) as store:
        meetings = tuple(meeting.to_dict() for meeting in store.list_meetings())
        memories = tuple(memory.to_dict() for memory in store.list())

    report = validate_database(db_path)
    moment = now or datetime.now(timezone.utc)
    snapshot = Snapshot(
        version=SNAPSHOT_VERSION,
        schema_version=report.schema_version,
        created_at=moment.isoformat(),
        meetings=meetings,
        memories=memories,
        checksum=_payload_checksum(meetings, memories),
    )
    if destination is not None:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(snapshot.to_json(), encoding="utf-8")
    return snapshot


def verify_snapshot(snapshot: Snapshot) -> bool:
    """Return whether the snapshot's stored checksum matches its contents."""
    return snapshot.checksum == _payload_checksum(snapshot.meetings, snapshot.memories)


def _load_snapshot(source: Snapshot | str | Path) -> Snapshot:
    if isinstance(source, Snapshot):
        return source
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    return Snapshot.from_dict(data)


def _to_meeting(data: dict[str, object]) -> StoredMeeting:
    participants = cast("list[str]", data.get("participants", []))
    duration = data.get("duration_seconds")
    return StoredMeeting(
        meeting_id=str(data["meeting_id"]),
        transcript_hash=str(data["transcript_hash"]),
        created_at=str(data["created_at"]),
        title=cast("str | None", data.get("title")),
        date=cast("str | None", data.get("date")),
        source=cast("str | None", data.get("source")),
        duration_seconds=float(cast("float", duration)) if duration is not None else None,
        participants=tuple(participants),
    )


def _to_memory(data: dict[str, object]) -> StoredMemory:
    evidence = tuple(
        StoredEvidence(
            utterance_index=int(cast("int", span["utterance_index"])),
            start=int(cast("int", span["start"])),
            end=int(cast("int", span["end"])),
            text=str(span["text"]),
        )
        for span in cast("list[dict[str, object]]", data.get("evidence", []))
    )
    metadata = {
        str(key): str(value)
        for key, value in cast("dict[str, object]", data.get("metadata", {})).items()
    }
    return StoredMemory(
        memory_id=str(data["memory_id"]),
        meeting_id=str(data["meeting_id"]),
        memory_type=str(data["memory_type"]),
        text=str(data["text"]),
        confidence=float(cast("float", data["confidence"])),
        utterance_index=int(cast("int", data["utterance_index"])),
        content_hash=str(data["content_hash"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        status=MemoryStatus(str(data["status"])),
        speaker=cast("str | None", data.get("speaker")),
        superseded_by=cast("str | None", data.get("superseded_by")),
        metadata=metadata,
        evidence=evidence,
    )


def import_snapshot(
    source: Snapshot | str | Path,
    db: str | Path,
    *,
    verify: bool = True,
) -> RecoveryReport:
    """Rebuild a database from a snapshot, restoring meetings and memories."""
    snapshot = _load_snapshot(source)
    if verify and not verify_snapshot(snapshot):
        raise BackupError("snapshot checksum mismatch; refusing to import corrupt data")

    db_path = Path(db)
    try:
        meetings = [_to_meeting(meeting) for meeting in snapshot.meetings]
        memories = [_to_memory(memory) for memory in snapshot.memories]
    except (KeyError, ValueError) as exc:
        raise BackupError(f"snapshot contains malformed records: {exc}") from exc

    with SQLiteMemoryStore(db_path) as store:
        for meeting in meetings:
            store.save_meeting(meeting)
        # Insert with ``superseded_by`` cleared first so the self-referential
        # foreign key never points at a not-yet-inserted row, then restore it.
        store.save_many(
            replace(memory, superseded_by=None) if memory.superseded_by else memory
            for memory in memories
        )
        for memory in memories:
            if memory.superseded_by:
                store.update(memory)

    return validate_database(db_path)
