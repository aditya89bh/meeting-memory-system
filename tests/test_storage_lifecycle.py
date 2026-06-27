"""Unit tests for memory lifecycle transitions and status-aware queries."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from meeting_memory.exceptions import MemoryNotFoundError
from meeting_memory.storage import (
    MemoryStatus,
    SQLiteMemoryStore,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
    memory_content_hash,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_LATER = datetime(2026, 2, 1, tzinfo=timezone.utc)


def _store_with_two_memories() -> SQLiteMemoryStore:
    store = SQLiteMemoryStore(":memory:")
    store.save_meeting(
        StoredMeeting(meeting_id="m1", transcript_hash="h1", created_at=_NOW.isoformat())
    )
    for index, (mid, mtype, text) in enumerate(
        [("m1:decision:0", "decision", "We decided to ship."), ("m1:risk:1", "risk", "a risk")]
    ):
        store.save(
            StoredMemory(
                memory_id=mid,
                meeting_id="m1",
                memory_type=mtype,
                text=text,
                confidence=0.9,
                utterance_index=index,
                content_hash=memory_content_hash(mtype, text),
                created_at=_NOW.isoformat(),
                updated_at=_NOW.isoformat(),
                speaker="Alice",
                evidence=(StoredEvidence(index, 0, 2, "We"),),
            )
        )
    return store


def test_archive_resolve_delete_restore() -> None:
    store = _store_with_two_memories()
    assert store.archive("m1:decision:0", now=_LATER).status is MemoryStatus.ARCHIVED
    assert store.resolve("m1:decision:0", now=_LATER).status is MemoryStatus.RESOLVED
    assert store.mark_deleted("m1:decision:0", now=_LATER).status is MemoryStatus.DELETED
    restored = store.restore("m1:decision:0", now=_LATER)
    assert restored.status is MemoryStatus.ACTIVE
    assert restored.updated_at == _LATER.isoformat()
    assert restored.created_at == _NOW.isoformat()
    store.close()


def test_supersede_records_pointer() -> None:
    store = _store_with_two_memories()
    superseded = store.supersede("m1:decision:0", "m1:risk:1", now=_LATER)
    assert superseded.status is MemoryStatus.SUPERSEDED
    assert superseded.superseded_by == "m1:risk:1"
    store.close()


def test_set_status_without_now_updates_timestamp() -> None:
    store = _store_with_two_memories()
    updated = store.set_status("m1:decision:0", MemoryStatus.ARCHIVED)
    assert updated.status is MemoryStatus.ARCHIVED
    assert updated.updated_at >= _NOW.isoformat()
    store.close()


def test_set_status_missing_raises() -> None:
    store = _store_with_two_memories()
    with pytest.raises(MemoryNotFoundError):
        store.set_status("ghost", MemoryStatus.ARCHIVED)
    store.close()


def test_status_queries() -> None:
    store = _store_with_two_memories()
    store.archive("m1:risk:1", now=_LATER)
    assert {m.memory_id for m in store.find_active()} == {"m1:decision:0"}
    archived = store.find_by_status(MemoryStatus.ARCHIVED)
    assert {m.memory_id for m in archived} == {"m1:risk:1"}
    store.close()
