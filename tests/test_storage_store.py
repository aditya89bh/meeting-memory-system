"""Unit tests for the SQLite memory store: CRUD, query, registry, migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from meeting_memory.exceptions import (
    DuplicateMeetingError,
    MeetingNotFoundError,
    MemoryNotFoundError,
    StorageError,
)
from meeting_memory.storage import (
    SCHEMA_VERSION,
    MemoryQuery,
    MemoryStatus,
    SQLiteMemoryStore,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
    memory_content_hash,
)

_STAMP = "2026-01-01T00:00:00+00:00"


def _store() -> SQLiteMemoryStore:
    return SQLiteMemoryStore(":memory:")


def _meeting(
    store: SQLiteMemoryStore,
    *,
    meeting_id: str = "m1",
    date: str | None = "2026-01-02",
    transcript_hash: str = "hash-1",
) -> StoredMeeting:
    stored = StoredMeeting(
        meeting_id=meeting_id,
        transcript_hash=transcript_hash,
        created_at=_STAMP,
        title="Title",
        date=date,
        source="/x.txt",
        duration_seconds=12.0,
        participants=("Alice", "Bob"),
    )
    store.save_meeting(stored)
    return stored


def _memory(
    *,
    meeting_id: str = "m1",
    memory_id: str = "m1:decision:0",
    memory_type: str = "decision",
    text: str = "We decided to ship.",
    confidence: float = 0.9,
    speaker: str | None = "Alice",
    utterance_index: int = 0,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    metadata: dict[str, str] | None = None,
) -> StoredMemory:
    return StoredMemory(
        memory_id=memory_id,
        meeting_id=meeting_id,
        memory_type=memory_type,
        text=text,
        confidence=confidence,
        utterance_index=utterance_index,
        content_hash=memory_content_hash(memory_type, text),
        created_at=_STAMP,
        updated_at=_STAMP,
        status=status,
        speaker=speaker,
        metadata=metadata or {"trigger": "decided"},
        evidence=(StoredEvidence(utterance_index, 0, 2, "We"),),
    )


def test_empty_database() -> None:
    store = _store()
    assert store.count() == 0
    assert store.list() == []
    assert store.exists("nope") is False
    with pytest.raises(MemoryNotFoundError):
        store.get("nope")
    store.close()


def test_save_and_get_round_trip() -> None:
    store = _store()
    _meeting(store)
    store.save(_memory(metadata={"trigger": "decided", "owner": "Alice"}))
    got = store.get("m1:decision:0")
    assert got.text == "We decided to ship."
    assert got.metadata == {"trigger": "decided", "owner": "Alice"}
    assert got.evidence[0].text == "We"
    assert store.exists("m1:decision:0") is True
    store.close()


def test_save_duplicate_id_raises() -> None:
    store = _store()
    _meeting(store)
    store.save(_memory())
    with pytest.raises(StorageError):
        store.save(_memory())
    store.close()


def test_save_without_meeting_violates_foreign_key() -> None:
    store = _store()
    with pytest.raises(StorageError):
        store.save(_memory(meeting_id="ghost"))
    store.close()


def test_save_many_counts_and_rejects_duplicates() -> None:
    store = _store()
    _meeting(store)
    stored = store.save_many(
        [
            _memory(memory_id="m1:decision:0"),
            _memory(memory_id="m1:risk:1", memory_type="risk", text="a risk", confidence=0.7),
        ]
    )
    assert stored == 2
    assert store.count() == 2
    with pytest.raises(StorageError):
        store.save_many([_memory(memory_id="m1:decision:0")])
    store.close()


def test_update_replaces_children() -> None:
    store = _store()
    _meeting(store)
    store.save(_memory(metadata={"trigger": "decided"}))
    updated = _memory(text="We decided to wait.", metadata={"trigger": "agreed"})
    store.update(updated)
    got = store.get("m1:decision:0")
    assert got.text == "We decided to wait."
    assert got.metadata == {"trigger": "agreed"}
    store.close()


def test_update_missing_raises() -> None:
    store = _store()
    _meeting(store)
    with pytest.raises(MemoryNotFoundError):
        store.update(_memory())
    store.close()


def test_delete_removes_memory_and_children() -> None:
    store = _store()
    _meeting(store)
    store.save(_memory())
    assert store.delete("m1:decision:0") is True
    assert store.delete("m1:decision:0") is False
    assert store.exists("m1:decision:0") is False
    store.close()


def test_list_ordering_limit_and_offset() -> None:
    store = _store()
    _meeting(store)
    store.save_many(
        [
            _memory(memory_id="m1:a", text="aaa"),
            _memory(memory_id="m1:b", memory_type="risk", text="bbb", confidence=0.6),
            _memory(memory_id="m1:c", memory_type="fact", text="ccc", confidence=0.5),
        ]
    )
    ids = [m.memory_id for m in store.list()]
    assert ids == ["m1:a", "m1:b", "m1:c"]
    assert [m.memory_id for m in store.list(limit=2)] == ["m1:a", "m1:b"]
    assert [m.memory_id for m in store.list(offset=1)] == ["m1:b", "m1:c"]
    store.close()


def test_query_filters_combine() -> None:
    store = _store()
    _meeting(store, meeting_id="m1", date="2026-01-02", transcript_hash="h1")
    _meeting(store, meeting_id="m2", date="2026-02-02", transcript_hash="h2")
    store.save_many(
        [
            _memory(memory_id="m1:decision:0", speaker="Alice", confidence=0.9),
            _memory(
                memory_id="m1:risk:1",
                memory_type="risk",
                text="a risk",
                speaker="Bob",
                confidence=0.6,
            ),
            _memory(
                memory_id="m2:decision:0",
                meeting_id="m2",
                speaker="Alice",
                text="We decided to grow.",
                confidence=0.95,
            ),
        ]
    )
    assert len(store.query(MemoryQuery(memory_types=frozenset({"risk"})))) == 1
    assert len(store.query(MemoryQuery(speakers=frozenset({"Alice"})))) == 2
    assert len(store.query(MemoryQuery(meeting_ids=frozenset({"m2"})))) == 1
    assert len(store.query(MemoryQuery(min_confidence=0.9))) == 2
    assert len(store.query(MemoryQuery(max_confidence=0.7))) == 1
    combined = store.query(
        MemoryQuery(speakers=frozenset({"Alice"}), memory_types=frozenset({"decision"}))
    )
    assert {m.memory_id for m in combined} == {"m1:decision:0", "m2:decision:0"}
    store.close()


def test_query_by_date_and_range() -> None:
    store = _store()
    _meeting(store, meeting_id="m1", date="2026-01-02", transcript_hash="h1")
    _meeting(store, meeting_id="m2", date="2026-03-02", transcript_hash="h2")
    store.save(_memory(memory_id="m1:d", meeting_id="m1"))
    store.save(_memory(memory_id="m2:d", meeting_id="m2", text="later decision"))
    assert len(store.query(MemoryQuery(on_date="2026-01-02"))) == 1
    assert len(store.query(MemoryQuery(date_from="2026-02-01", date_to="2026-04-01"))) == 1
    assert len(store.query(MemoryQuery(date_from="2026-01-01"))) == 2
    store.close()


def test_query_ordering_and_unknown_order_by() -> None:
    store = _store()
    _meeting(store)
    store.save(_memory(memory_id="m1:lo", text="lo", confidence=0.3))
    store.save(_memory(memory_id="m1:hi", memory_type="risk", text="hi", confidence=0.9))
    ordered = store.query(MemoryQuery(order_by="confidence", descending=True))
    assert [m.memory_id for m in ordered] == ["m1:hi", "m1:lo"]
    with pytest.raises(StorageError):
        store.query(MemoryQuery(order_by="bogus"))
    store.close()


def test_query_limit_offset() -> None:
    store = _store()
    _meeting(store)
    store.save_many(
        [
            _memory(memory_id="m1:a", text="aaa"),
            _memory(memory_id="m1:b", memory_type="risk", text="bbb", confidence=0.6),
        ]
    )
    assert len(store.query(MemoryQuery(limit=1))) == 1
    assert [m.memory_id for m in store.query(MemoryQuery(offset=1))] == ["m1:b"]
    store.close()


def test_count_with_and_without_query() -> None:
    store = _store()
    _meeting(store)
    store.save(_memory())
    store.save(_memory(memory_id="m1:risk:1", memory_type="risk", text="r", confidence=0.6))
    assert store.count() == 2
    assert store.count(MemoryQuery(memory_types=frozenset({"risk"}))) == 1
    store.close()


def test_meeting_registry_round_trip() -> None:
    store = _store()
    meeting = _meeting(store)
    assert store.meeting_exists("m1") is True
    assert store.get_meeting("m1").title == "Title"
    assert store.find_meeting_by_hash(meeting.transcript_hash).meeting_id == "m1"
    assert store.find_meeting_by_hash("missing") is None
    store.close()


def test_get_missing_meeting_raises() -> None:
    store = _store()
    with pytest.raises(MeetingNotFoundError):
        store.get_meeting("ghost")
    store.close()


def test_duplicate_meeting_by_id_and_hash() -> None:
    store = _store()
    _meeting(store, meeting_id="m1", transcript_hash="h1")
    with pytest.raises(DuplicateMeetingError):
        _meeting(store, meeting_id="m1", transcript_hash="h-other")
    with pytest.raises(DuplicateMeetingError):
        _meeting(store, meeting_id="m-other", transcript_hash="h1")
    store.close()


def test_save_meeting_integrity_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store()
    _meeting(store, meeting_id="m1", transcript_hash="h1")
    # Bypass the pre-checks so the database constraint itself trips.
    monkeypatch.setattr(store, "meeting_exists", lambda _id: False)
    monkeypatch.setattr(store, "find_meeting_by_hash", lambda _h: None)
    with pytest.raises(DuplicateMeetingError):
        _meeting(store, meeting_id="m1", transcript_hash="h2")
    store.close()


def test_list_meetings_orders_undated_last() -> None:
    store = _store()
    _meeting(store, meeting_id="b", date="2026-02-02", transcript_hash="h2")
    _meeting(store, meeting_id="a", date="2026-01-02", transcript_hash="h1")
    _meeting(store, meeting_id="z", date=None, transcript_hash="h3")
    assert [m.meeting_id for m in store.list_meetings()] == ["a", "b", "z"]
    assert [m.meeting_id for m in store.list_meetings(limit=1)] == ["a"]
    store.close()


def test_delete_meeting_cascades() -> None:
    store = _store()
    _meeting(store)
    store.save(_memory())
    assert store.delete_meeting("m1") is True
    assert store.count() == 0
    assert store.delete_meeting("m1") is False
    store.close()


def test_schema_version_and_indexes(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "memory.db"
    store = SQLiteMemoryStore(db)
    version = store._connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION == 1
    index_names = {
        row[0]
        for row in store._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    assert "idx_memories_type" in index_names
    assert "idx_memories_content_hash" in index_names
    store.close()
    assert db.exists()


def test_reopen_existing_database_is_noop(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    first = SQLiteMemoryStore(db)
    _meeting(first)
    first.save(_memory())
    first.close()
    second = SQLiteMemoryStore(db)
    assert second.count() == 1
    assert second._connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    second.close()


def test_corrupt_database_raises(tmp_path: Path) -> None:
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"this is definitely not a sqlite database file" * 10)
    with pytest.raises(sqlite3.DatabaseError):
        SQLiteMemoryStore(db)


def test_context_manager_closes() -> None:
    with SQLiteMemoryStore(":memory:") as store:
        _meeting(store)
        store.save(_memory())
        assert store.count() == 1
    with pytest.raises(sqlite3.ProgrammingError):
        store.count()
