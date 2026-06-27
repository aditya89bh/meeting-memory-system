"""Bridge extracted memories into the persistent store.

This module converts an in-memory :class:`ExtractionResult` (plus its source
:class:`Meeting`) into stored records and writes them to a
:class:`~meeting_memory.storage.base.MemoryStore` as a single logical unit: the
meeting registry row first, then every extracted memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..extraction.models import ExtractionResult
from ..models import Meeting
from .base import MemoryStore
from .models import MemoryStatus, StoredMeeting, StoredMemory


@dataclass(frozen=True)
class PersistResult:
    """Outcome of persisting one extraction result."""

    meeting: StoredMeeting
    stored: tuple[StoredMemory, ...]

    @property
    def stored_count(self) -> int:
        """Number of memories written to the store."""
        return len(self.stored)


def persist_extraction(
    store: MemoryStore,
    meeting: Meeting,
    result: ExtractionResult,
    *,
    transcript_hash: str,
    created_at: datetime,
    status: MemoryStatus = MemoryStatus.ACTIVE,
) -> PersistResult:
    """Persist a meeting and all of its extracted memories.

    The meeting is registered first so memory foreign keys resolve. Every memory
    is stored with the given ``status`` (``ACTIVE`` by default) and stamped with
    ``created_at`` for reproducible timestamps.
    """
    stored_meeting = StoredMeeting.from_meeting(
        meeting,
        meeting_id=result.meeting_id,
        transcript_hash=transcript_hash,
        created_at=created_at,
    )
    store.save_meeting(stored_meeting)

    stored_memories = tuple(
        StoredMemory.from_extracted(memory, created_at=created_at, status=status)
        for memory in result.memories
    )
    store.save_many(stored_memories)
    return PersistResult(meeting=stored_meeting, stored=stored_memories)
