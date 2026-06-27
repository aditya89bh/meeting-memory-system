"""Typed records and query model for the persistent storage layer.

These are plain, immutable data carriers that mirror the database rows. They are
database-agnostic: a :class:`~meeting_memory.storage.base.MemoryStore`
implementation is responsible for mapping them to and from its own rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..extraction.models import CommitmentMemory, ExtractedMemory
from ..models import Meeting
from ..utils import meeting_duration
from .hashing import memory_content_hash


class MemoryStatus(str, Enum):
    """Lifecycle state of a stored memory."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"
    DELETED = "deleted"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class StoredEvidence:
    """A persisted evidence span pointing at the source utterance."""

    utterance_index: int
    start: int
    end: int
    text: str

    def to_dict(self) -> dict[str, object]:
        """Serialise the evidence span into JSON-compatible primitives."""
        return {
            "utterance_index": self.utterance_index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }


@dataclass(frozen=True)
class StoredMeeting:
    """A meeting persisted in the registry."""

    meeting_id: str
    transcript_hash: str
    created_at: str
    title: str | None = None
    date: str | None = None
    source: str | None = None
    duration_seconds: float | None = None
    participants: tuple[str, ...] = ()

    @classmethod
    def from_meeting(
        cls,
        meeting: Meeting,
        *,
        meeting_id: str,
        transcript_hash: str,
        created_at: datetime,
    ) -> StoredMeeting:
        """Build a registry record from a parsed :class:`Meeting`."""
        metadata = meeting.metadata
        return cls(
            meeting_id=meeting_id,
            transcript_hash=transcript_hash,
            created_at=created_at.isoformat(),
            title=metadata.title,
            date=metadata.date.isoformat() if metadata.date else None,
            source=metadata.source_path,
            duration_seconds=meeting_duration(meeting),
            participants=tuple(meeting.speakers),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialise the meeting record into JSON-compatible primitives."""
        return {
            "meeting_id": self.meeting_id,
            "title": self.title,
            "date": self.date,
            "source": self.source,
            "duration_seconds": self.duration_seconds,
            "participants": list(self.participants),
            "transcript_hash": self.transcript_hash,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class StoredMemory:
    """A single extracted memory persisted in the store."""

    memory_id: str
    meeting_id: str
    memory_type: str
    text: str
    confidence: float
    utterance_index: int
    content_hash: str
    created_at: str
    updated_at: str
    status: MemoryStatus = MemoryStatus.ACTIVE
    speaker: str | None = None
    superseded_by: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    evidence: tuple[StoredEvidence, ...] = ()

    @classmethod
    def from_extracted(
        cls,
        memory: ExtractedMemory,
        *,
        created_at: datetime,
        status: MemoryStatus = MemoryStatus.ACTIVE,
    ) -> StoredMemory:
        """Build a storage record from an extracted memory.

        Commitment owner/due fields are folded into ``metadata`` so the storage
        record stays uniform across memory types.
        """
        metadata = dict(memory.metadata)
        if isinstance(memory, CommitmentMemory):
            if memory.owner is not None:
                metadata["owner"] = memory.owner
            if memory.due is not None:
                metadata["due"] = memory.due

        stamp = created_at.isoformat()
        evidence = (
            StoredEvidence(
                utterance_index=memory.evidence.utterance_index,
                start=memory.evidence.start,
                end=memory.evidence.end,
                text=memory.evidence.text,
            ),
        )
        return cls(
            memory_id=memory.memory_id,
            meeting_id=memory.meeting_id,
            memory_type=memory.memory_type.value,
            text=memory.text,
            confidence=memory.confidence,
            utterance_index=memory.utterance_index,
            content_hash=memory_content_hash(memory.memory_type.value, memory.text),
            created_at=stamp,
            updated_at=stamp,
            status=status,
            speaker=memory.speaker,
            metadata=metadata,
            evidence=evidence,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialise the memory record into JSON-compatible primitives."""
        return {
            "memory_id": self.memory_id,
            "meeting_id": self.meeting_id,
            "memory_type": self.memory_type,
            "speaker": self.speaker,
            "text": self.text,
            "confidence": self.confidence,
            "utterance_index": self.utterance_index,
            "status": self.status.value,
            "superseded_by": self.superseded_by,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "evidence": [span.to_dict() for span in self.evidence],
        }


@dataclass(frozen=True)
class MemoryQuery:
    """A deterministic filter over stored memories.

    All populated filters are combined with logical AND. ``None`` (or an empty
    collection) means "do not filter on this field". Date filters compare against
    the owning meeting's date.
    """

    memory_types: frozenset[str] | None = None
    speakers: frozenset[str] | None = None
    meeting_ids: frozenset[str] | None = None
    statuses: frozenset[MemoryStatus] | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    on_date: str | None = None
    order_by: str = "created_at"
    descending: bool = False
    limit: int | None = None
    offset: int = 0
