"""Unit tests for the import pipeline, persistence bridge, and duplicate detection."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from meeting_memory.extraction import ExtractionConfig, extract_memories
from meeting_memory.parser import parse_text
from meeting_memory.storage import (
    SQLiteMemoryStore,
    import_meeting,
    is_duplicate,
    persist_extraction,
    transcript_hash,
)
from meeting_memory.storage.dedup import filter_duplicates
from meeting_memory.storage.importer import ImportResult
from meeting_memory.storage.models import StoredMeeting, StoredMemory

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_TRANSCRIPT = "\n".join(
    [
        "Alice: We decided to adopt Postgres.",
        "Bob: I will send the report by Friday.",
        "Alice: There is a risk the migration fails.",
    ]
)


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_import_meeting_persists_and_summarises(tmp_path: Path) -> None:
    path = _write(tmp_path, "imp.txt", _TRANSCRIPT)
    store = SQLiteMemoryStore(":memory:")
    result = import_meeting(path, store, now=_NOW)
    assert result.duplicate is False
    assert result.meeting.meeting_id == "imp"
    assert result.stored_count == 3
    assert result.counts == {"decision": 1, "commitment": 1, "risk": 1}
    assert store.count() == 3
    lines = result.summary_lines()
    assert lines[0] == "Meeting imported: imp"
    assert "3 memories stored" in lines
    assert "1 decision" in lines
    store.close()


def test_import_to_dict(tmp_path: Path) -> None:
    path = _write(tmp_path, "imp.txt", _TRANSCRIPT)
    store = SQLiteMemoryStore(":memory:")
    payload = import_meeting(path, store, now=_NOW).to_dict()
    assert payload["stored_count"] == 3
    assert payload["duplicate"] is False
    assert payload["meeting"]["meeting_id"] == "imp"
    store.close()


def test_reimport_same_transcript_is_duplicate(tmp_path: Path) -> None:
    path = _write(tmp_path, "imp.txt", _TRANSCRIPT)
    store = SQLiteMemoryStore(":memory:")
    import_meeting(path, store, now=_NOW)
    result = import_meeting(path, store, now=_NOW)
    assert result.duplicate is True
    assert result.stored_count == 0
    assert result.summary_lines() == [
        "Meeting already imported: imp",
        "0 memories stored (duplicate transcript)",
    ]
    assert store.count() == 3
    store.close()


def test_import_meeting_id_collision_is_duplicate(tmp_path: Path) -> None:
    first = _write(tmp_path / "a", "meeting.txt", _TRANSCRIPT)
    second = _write(tmp_path / "b", "meeting.txt", "Carol: We decided to wait.")
    store = SQLiteMemoryStore(":memory:")
    import_meeting(first, store, now=_NOW)
    result = import_meeting(second, store, now=_NOW)
    assert result.duplicate is True
    assert result.meeting.meeting_id == "meeting"
    store.close()


def test_import_without_now_uses_current_time(tmp_path: Path) -> None:
    path = _write(tmp_path, "imp.txt", _TRANSCRIPT)
    store = SQLiteMemoryStore(":memory:")
    result = import_meeting(path, store)
    assert result.stored_count == 3
    store.close()


def test_import_memory_level_dedup_skips(tmp_path: Path) -> None:
    content = "\n".join(
        [
            "Alice: We decided to adopt Postgres.",
            "Bob: We decided to adopt Postgres.",
        ]
    )
    path = _write(tmp_path, "dup.txt", content)
    store = SQLiteMemoryStore(":memory:")
    result = import_meeting(path, store, now=_NOW, config=ExtractionConfig(deduplicate=False))
    assert result.skipped_duplicates == 1
    assert result.stored_count == 1
    assert "1 duplicate memories skipped" in result.summary_lines()
    store.close()


def test_persist_extraction_without_dedup(tmp_path: Path) -> None:
    meeting = parse_text(_TRANSCRIPT, source_path=str(tmp_path / "p.txt"))
    result = extract_memories(meeting, now=_NOW)
    store = SQLiteMemoryStore(":memory:")
    persisted = persist_extraction(
        store,
        meeting,
        result,
        transcript_hash=transcript_hash(_TRANSCRIPT),
        created_at=_NOW,
        deduplicate=False,
    )
    assert persisted.stored_count == 3
    assert persisted.skipped_count == 0
    store.close()


def _stored(memory_id: str, content_hash: str, confidence: float) -> StoredMemory:
    return StoredMemory(
        memory_id=memory_id,
        meeting_id="m1",
        memory_type="risk",
        text="text",
        confidence=confidence,
        utterance_index=0,
        content_hash=content_hash,
        created_at=_NOW.isoformat(),
        updated_at=_NOW.isoformat(),
    )


def test_is_duplicate_respects_hash_and_threshold() -> None:
    a = _stored("a", "h", 0.9)
    b = _stored("b", "h", 0.5)
    c = _stored("c", "other", 0.9)
    assert is_duplicate(a, b, threshold=1.0) is True
    assert is_duplicate(a, b, threshold=0.1) is False
    assert is_duplicate(a, c, threshold=1.0) is False


def test_filter_duplicates_against_existing_rows() -> None:
    store = SQLiteMemoryStore(":memory:")
    store.save_meeting(
        StoredMeeting(meeting_id="m1", transcript_hash="h1", created_at=_NOW.isoformat())
    )
    store.save(_stored("m1:risk:0", "shared", 0.9))
    candidates = (_stored("m1:risk:1", "shared", 0.9), _stored("m1:risk:2", "fresh", 0.8))
    to_store, skipped = filter_duplicates(store, "m1", candidates, threshold=1.0)
    assert [m.memory_id for m in to_store] == ["m1:risk:2"]
    assert [m.memory_id for m in skipped] == ["m1:risk:1"]
    store.close()


def test_import_result_summary_without_skips() -> None:
    meeting = StoredMeeting(meeting_id="m", transcript_hash="h", created_at=_NOW.isoformat())
    result = ImportResult(meeting=meeting, stored_count=0, counts={})
    assert result.summary_lines() == ["Meeting imported: m", "0 memories stored"]
