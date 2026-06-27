"""Shared builders for intelligence tests.

These helpers construct ``StoredMeeting``/``StoredMemory`` records directly and
load them into an in-memory store, so intelligence analyses can be exercised
deterministically without parsing transcripts.
"""

from __future__ import annotations

from meeting_memory.storage import (
    MemoryStatus,
    SQLiteMemoryStore,
    StoredMeeting,
    StoredMemory,
)


def make_meeting(
    meeting_id: str,
    *,
    date: str,
    title: str | None = None,
    participants: tuple[str, ...] = ("Alice", "Bob"),
) -> StoredMeeting:
    """Build a stored meeting with a deterministic creation timestamp."""
    return StoredMeeting(
        meeting_id=meeting_id,
        transcript_hash=f"hash-{meeting_id}",
        created_at=f"{date}T09:00:00+00:00",
        title=title or f"Meeting {meeting_id}",
        date=date,
        participants=participants,
    )


def make_memory(
    memory_id: str,
    memory_type: str,
    text: str,
    *,
    meeting_id: str,
    created_at: str,
    updated_at: str | None = None,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    speaker: str | None = "Alice",
    superseded_by: str | None = None,
    content_hash: str | None = None,
    metadata: dict[str, str] | None = None,
) -> StoredMemory:
    """Build a stored memory; ``content_hash`` defaults to the text for grouping."""
    return StoredMemory(
        memory_id=memory_id,
        meeting_id=meeting_id,
        memory_type=memory_type,
        text=text,
        confidence=0.9,
        utterance_index=1,
        content_hash=content_hash or text,
        created_at=created_at,
        updated_at=updated_at or created_at,
        status=status,
        speaker=speaker,
        superseded_by=superseded_by,
        metadata=metadata or {},
    )


def load_store(meetings: list[StoredMeeting], memories: list[StoredMemory]) -> SQLiteMemoryStore:
    """Return an in-memory store populated with the given meetings and memories."""
    store = SQLiteMemoryStore(":memory:")
    for meeting in meetings:
        store.save_meeting(meeting)
    # Insert in dependency order so ``superseded_by`` foreign keys resolve.
    pending = list(memories)
    inserted: set[str] = set()
    while pending:
        progressed = False
        for memory in list(pending):
            if memory.superseded_by is None or memory.superseded_by in inserted:
                store.save(memory)
                inserted.add(memory.memory_id)
                pending.remove(memory)
                progressed = True
        if not progressed:
            for memory in pending:
                store.save(memory)
            break
    return store
