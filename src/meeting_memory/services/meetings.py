"""Meeting-oriented service: importing transcripts and reading meeting records."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..connectors import ImportRequest, ImportResult, StructuredLogger, default_manager
from ..extraction import MemoryType
from ..storage import MemoryQuery, MemoryStatus, SQLiteMemoryStore, StoredMeeting

_FORMAT_SUFFIX = {
    "text": ".txt",
    "txt": ".txt",
    "json": ".json",
    "markdown": ".md",
    "md": ".md",
    "csv": ".csv",
}


@dataclass(frozen=True)
class MeetingStats:
    """Aggregate counts across the whole store (used by overview/dashboard)."""

    meetings: int
    memories: int
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialise the stats into JSON-compatible primitives."""
        return {
            "meetings": self.meetings,
            "memories": self.memories,
            "by_type": dict(self.by_type),
            "by_status": dict(self.by_status),
        }


class MeetingService:
    """Import transcripts and read stored meetings via the connector pipeline."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    def import_path(
        self,
        source: str | Path,
        *,
        recursive: bool = False,
        pattern: str = "*",
        deduplicate: bool = True,
        dry_run: bool = False,
        now: str | None = None,
        min_confidence: float = 0.0,
        memory_types: frozenset[str] = frozenset(),
        limit: int | None = None,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Import a file, directory, or archive, reusing the connector manager."""
        request = ImportRequest(
            source=str(source),
            recursive=recursive,
            pattern=pattern,
            deduplicate=deduplicate,
            dry_run=dry_run,
            now=now,
            min_confidence=min_confidence,
            memory_types=memory_types,
            limit=limit,
        )
        manager = default_manager()
        if dry_run:
            return manager.dry_run_import(request, logger=logger)
        with SQLiteMemoryStore(self.db) as store:
            return manager.import_source(request, store, logger=logger)

    def import_content(
        self,
        content: str,
        fmt: str = "text",
        *,
        deduplicate: bool = True,
        dry_run: bool = False,
        now: str | None = None,
    ) -> ImportResult:
        """Import a transcript provided as raw text in a supported format."""
        suffix = _FORMAT_SUFFIX.get(fmt.lower(), ".txt")
        with tempfile.TemporaryDirectory(prefix="mm-import-") as tmp:
            path = Path(tmp) / f"upload{suffix}"
            path.write_text(content, encoding="utf-8")
            return self.import_path(path, deduplicate=deduplicate, dry_run=dry_run, now=now)

    def list_meetings(self, *, limit: int | None = None, offset: int = 0) -> list[StoredMeeting]:
        """Return stored meetings (most recently created first is store-defined)."""
        with SQLiteMemoryStore(self.db) as store:
            return store.list_meetings(limit=limit, offset=offset)

    def count_meetings(self) -> int:
        """Return the total number of stored meetings."""
        with SQLiteMemoryStore(self.db) as store:
            return len(store.list_meetings())

    def get_meeting(self, meeting_id: str) -> StoredMeeting:
        """Return a single meeting by id (raises ``MeetingNotFoundError``)."""
        with SQLiteMemoryStore(self.db) as store:
            return store.get_meeting(meeting_id)

    def stats(self) -> MeetingStats:
        """Compute store-wide counts by memory type and lifecycle status."""
        with SQLiteMemoryStore(self.db) as store:
            meetings = len(store.list_meetings())
            total = store.count()
            by_type = {
                member.value: store.count(MemoryQuery(memory_types=frozenset({member.value})))
                for member in MemoryType
            }
            by_status = {
                member.value: store.count(MemoryQuery(statuses=frozenset({member})))
                for member in MemoryStatus
            }
        return MeetingStats(meetings=meetings, memories=total, by_type=by_type, by_status=by_status)
