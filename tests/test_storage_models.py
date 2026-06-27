"""Unit tests for storage data models and hashing helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from meeting_memory.extraction.models import CommitmentMemory, EvidenceSpan
from meeting_memory.parser import parse_text
from meeting_memory.storage import (
    MemoryStatus,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
    memory_content_hash,
    transcript_hash,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_memory_status_is_str_enum() -> None:
    assert MemoryStatus.ACTIVE == "active"
    assert str(MemoryStatus.SUPERSEDED) == "superseded"


def test_stored_evidence_to_dict() -> None:
    span = StoredEvidence(utterance_index=2, start=0, end=4, text="risk")
    assert span.to_dict() == {
        "utterance_index": 2,
        "start": 0,
        "end": 4,
        "text": "risk",
    }


def test_transcript_hash_is_stable_and_distinct() -> None:
    assert transcript_hash("hello") == transcript_hash("hello")
    assert transcript_hash("hello") != transcript_hash("world")


def test_memory_content_hash_normalizes_text() -> None:
    a = memory_content_hash("risk", "The   migration  MIGHT fail.")
    b = memory_content_hash("risk", "the migration might fail")
    assert a == b


def test_memory_content_hash_depends_on_type() -> None:
    assert memory_content_hash("risk", "same text") != memory_content_hash("decision", "same text")


def test_stored_meeting_from_meeting() -> None:
    text = "---\ntitle: Sync\ndate: 2026-01-02\n---\n[00:00:00] Alice: We decided to ship."
    meeting = parse_text(text, source_path="/tmp/sync.txt")
    stored = StoredMeeting.from_meeting(
        meeting, meeting_id="sync", transcript_hash="abc", created_at=_NOW
    )
    payload = stored.to_dict()
    assert payload["meeting_id"] == "sync"
    assert payload["title"] == "Sync"
    assert payload["date"] == "2026-01-02"
    assert payload["source"] == "/tmp/sync.txt"
    assert payload["participants"] == ["Alice"]
    assert payload["transcript_hash"] == "abc"
    assert payload["created_at"] == _NOW.isoformat()


def test_stored_meeting_from_meeting_without_metadata_date() -> None:
    meeting = parse_text("Alice: We decided to ship.")
    stored = StoredMeeting.from_meeting(
        meeting, meeting_id="m", transcript_hash="h", created_at=_NOW
    )
    assert stored.date is None


def test_stored_memory_from_extracted_folds_commitment_fields() -> None:
    memory = CommitmentMemory(
        memory_id="m:commitment:0",
        text="Dana will send the report by Friday.",
        meeting_id="m",
        utterance_index=1,
        evidence=EvidenceSpan(utterance_index=1, start=0, end=4, text="Dana"),
        confidence=0.9,
        speaker="Marco",
        metadata={"trigger": "will"},
        owner="Dana",
        due="Friday",
    )
    stored = StoredMemory.from_extracted(memory, created_at=_NOW)
    assert stored.status is MemoryStatus.ACTIVE
    assert stored.memory_type == "commitment"
    assert stored.metadata == {"trigger": "will", "owner": "Dana", "due": "Friday"}
    assert stored.content_hash == memory_content_hash("commitment", memory.text)
    assert stored.created_at == stored.updated_at == _NOW.isoformat()
    assert stored.evidence[0].text == "Dana"


def test_stored_memory_to_dict_round_trips_fields() -> None:
    memory = CommitmentMemory(
        memory_id="m:commitment:0",
        text="I will follow up.",
        meeting_id="m",
        utterance_index=0,
        evidence=EvidenceSpan(utterance_index=0, start=0, end=1, text="I"),
        confidence=0.8,
    )
    stored = StoredMemory.from_extracted(memory, created_at=_NOW, status=MemoryStatus.ARCHIVED)
    payload = stored.to_dict()
    assert payload["status"] == "archived"
    assert payload["superseded_by"] is None
    assert payload["evidence"] == [{"utterance_index": 0, "start": 0, "end": 1, "text": "I"}]
