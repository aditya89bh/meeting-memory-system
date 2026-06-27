"""Unit tests for the convenience query helpers on the store."""

from __future__ import annotations

from datetime import datetime, timezone

from meeting_memory.storage import (
    SQLiteMemoryStore,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
    memory_content_hash,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _populated() -> SQLiteMemoryStore:
    store = SQLiteMemoryStore(":memory:")
    store.save_meeting(
        StoredMeeting(
            meeting_id="m1",
            transcript_hash="h1",
            created_at=_NOW.isoformat(),
            date="2026-01-02",
        )
    )
    store.save_meeting(
        StoredMeeting(
            meeting_id="m2",
            transcript_hash="h2",
            created_at=_NOW.isoformat(),
            date="2026-03-02",
        )
    )
    rows = [
        ("m1:decision:0", "m1", "decision", "We decided to ship.", 0.95, "Alice"),
        ("m1:risk:1", "m1", "risk", "a risk", 0.6, "Bob"),
        ("m2:decision:0", "m2", "decision", "We decided to grow.", 0.8, "Alice"),
    ]
    for memory_id, meeting_id, mtype, text, conf, speaker in rows:
        store.save(
            StoredMemory(
                memory_id=memory_id,
                meeting_id=meeting_id,
                memory_type=mtype,
                text=text,
                confidence=conf,
                utterance_index=0,
                content_hash=memory_content_hash(mtype, text),
                created_at=_NOW.isoformat(),
                updated_at=_NOW.isoformat(),
                speaker=speaker,
                evidence=(StoredEvidence(0, 0, 2, "We"),),
            )
        )
    return store


def test_find_by_type() -> None:
    store = _populated()
    assert {m.memory_id for m in store.find_by_type("decision")} == {
        "m1:decision:0",
        "m2:decision:0",
    }
    store.close()


def test_find_by_speaker() -> None:
    store = _populated()
    assert len(store.find_by_speaker("Alice")) == 2
    store.close()


def test_find_by_meeting() -> None:
    store = _populated()
    assert {m.memory_id for m in store.find_by_meeting("m2")} == {"m2:decision:0"}
    store.close()


def test_find_by_confidence_range() -> None:
    store = _populated()
    assert len(store.find_by_confidence(0.9)) == 1
    assert len(store.find_by_confidence(0.7, 0.9)) == 1
    store.close()


def test_find_by_date_and_between_dates() -> None:
    store = _populated()
    assert len(store.find_by_date("2026-01-02")) == 2
    assert len(store.find_between_dates("2026-02-01", "2026-04-01")) == 1
    store.close()
