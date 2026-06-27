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
from .dedup import filter_duplicates
from .models import MemoryStatus, StoredMeeting, StoredMemory


@dataclass(frozen=True)
class PersistResult:
    """Outcome of persisting one extraction result."""

    meeting: StoredMeeting
    stored: tuple[StoredMemory, ...]
    skipped: tuple[StoredMemory, ...] = ()

    @property
    def stored_count(self) -> int:
        """Number of memories written to the store."""
        return len(self.stored)

    @property
    def skipped_count(self) -> int:
        """Number of candidate memories skipped as duplicates."""
        return len(self.skipped)


def persist_extraction(
    store: MemoryStore,
    meeting: Meeting,
    result: ExtractionResult,
    *,
    transcript_hash: str,
    created_at: datetime,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    deduplicate: bool = True,
    dedup_threshold: float = 1.0,
) -> PersistResult:
    """Persist a meeting and its extracted memories.

    The meeting is registered first so memory foreign keys resolve. Every memory
    is stored with the given ``status`` (``ACTIVE`` by default) and stamped with
    ``created_at`` for reproducible timestamps. When ``deduplicate`` is set,
    memories that duplicate one already present in the meeting (within
    ``dedup_threshold`` confidence) are skipped.
    """
    stored_meeting = StoredMeeting.from_meeting(
        meeting,
        meeting_id=result.meeting_id,
        transcript_hash=transcript_hash,
        created_at=created_at,
    )
    store.save_meeting(stored_meeting)

    candidates = tuple(
        StoredMemory.from_extracted(memory, created_at=created_at, status=status)
        for memory in result.memories
    )
    if deduplicate:
        to_store, skipped = filter_duplicates(
            store, result.meeting_id, candidates, threshold=dedup_threshold
        )
    else:
        to_store, skipped = candidates, ()

    store.save_many(to_store)
    return PersistResult(meeting=stored_meeting, stored=to_store, skipped=skipped)
