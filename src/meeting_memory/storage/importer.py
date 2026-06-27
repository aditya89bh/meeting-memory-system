"""End-to-end import pipeline: load -> parse -> extract -> persist.

A single call turns a transcript file on disk into durable organizational
memory and returns a structured summary. Re-importing the same transcript is a
deterministic no-op thanks to the transcript hash recorded in the registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..exceptions import DuplicateMeetingError
from ..extraction import ExtractionConfig, extract_memories
from ..parser import MeetingParser
from .base import MemoryStore
from .hashing import transcript_hash
from .models import MemoryStatus, StoredMeeting, StoredMemory
from .persistence import persist_extraction


@dataclass(frozen=True)
class ImportResult:
    """Summary of a single import."""

    meeting: StoredMeeting
    stored_count: int
    counts: dict[str, int] = field(default_factory=dict)
    duplicate: bool = False
    skipped_duplicates: int = 0

    def summary_lines(self) -> list[str]:
        """Human-readable summary lines for CLI output."""
        if self.duplicate:
            return [
                f"Meeting already imported: {self.meeting.meeting_id}",
                "0 memories stored (duplicate transcript)",
            ]
        lines = [
            f"Meeting imported: {self.meeting.meeting_id}",
            f"{self.stored_count} memories stored",
        ]
        for memory_type, count in self.counts.items():
            label = memory_type.replace("_", " ")
            plural = label if count == 1 else f"{label}s"
            lines.append(f"{count} {plural}")
        if self.skipped_duplicates:
            lines.append(f"{self.skipped_duplicates} duplicate memories skipped")
        return lines

    def to_dict(self) -> dict[str, object]:
        """Serialise the import summary into JSON-compatible primitives."""
        return {
            "meeting": self.meeting.to_dict(),
            "stored_count": self.stored_count,
            "counts": dict(self.counts),
            "duplicate": self.duplicate,
            "skipped_duplicates": self.skipped_duplicates,
        }


def import_meeting(
    path: str | Path,
    store: MemoryStore,
    *,
    config: ExtractionConfig | None = None,
    now: datetime | None = None,
    status: MemoryStatus = MemoryStatus.ACTIVE,
) -> ImportResult:
    """Import a transcript file into ``store`` and return a summary."""
    source = Path(path)
    created_at = now if now is not None else datetime.now(timezone.utc)

    raw_text = source.read_text(encoding="utf-8")
    digest = transcript_hash(raw_text)

    existing = store.find_meeting_by_hash(digest)
    if existing is not None:
        return ImportResult(meeting=existing, stored_count=0, duplicate=True)

    meeting = MeetingParser().parse_file(source)
    result = extract_memories(meeting, config=config, now=created_at)

    try:
        persisted = persist_extraction(
            store,
            meeting,
            result,
            transcript_hash=digest,
            created_at=created_at,
            status=status,
        )
    except DuplicateMeetingError:
        existing = store.get_meeting(result.meeting_id)
        return ImportResult(meeting=existing, stored_count=0, duplicate=True)

    counts = _counts_by_type(persisted.stored)
    return ImportResult(
        meeting=persisted.meeting,
        stored_count=persisted.stored_count,
        counts=counts,
    )


def _counts_by_type(memories: tuple[StoredMemory, ...]) -> dict[str, int]:
    """Count stored memories per type in stable insertion order."""
    counts: dict[str, int] = {}
    for memory in memories:
        counts[memory.memory_type] = counts.get(memory.memory_type, 0) + 1
    return counts
