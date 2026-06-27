"""Typed models for extracted meeting memory.

Every extracted item is an immutable :class:`ExtractedMemory` subclass carrying
enough provenance to be auditable: which meeting and utterance it came from, the
exact text span that triggered it, a bounded confidence score, and the time it
was produced. :class:`ExtractionResult` aggregates the items for a single
meeting along with any warnings raised during extraction.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar


class MemoryType(str, Enum):
    """The kind of memory primitive an extracted record represents."""

    DECISION = "decision"
    COMMITMENT = "commitment"
    OPEN_LOOP = "open_loop"
    RISK = "risk"
    ASSUMPTION = "assumption"
    QUESTION = "question"
    FACT = "fact"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class EvidenceSpan:
    """A reference to the exact text that justifies an extracted memory.

    Attributes:
        utterance_index: Index of the source utterance within the meeting.
        start: Character offset (inclusive) of the span in the utterance text.
        end: Character offset (exclusive) of the span in the utterance text.
        text: The literal substring that triggered the extraction.
    """

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
class ExtractedMemory:
    """Base class for a single extracted memory record.

    Subclasses fix :attr:`memory_type` via a class variable; all other fields are
    shared. Instances are immutable so a produced record is a stable value.
    """

    memory_type: ClassVar[MemoryType]

    memory_id: str
    text: str
    meeting_id: str
    utterance_index: int
    evidence: EvidenceSpan
    confidence: float
    speaker: str | None = None
    extracted_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialise the memory record into JSON-compatible primitives."""
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type.value,
            "text": self.text,
            "speaker": self.speaker,
            "meeting_id": self.meeting_id,
            "utterance_index": self.utterance_index,
            "evidence": self.evidence.to_dict(),
            "confidence": self.confidence,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DecisionMemory(ExtractedMemory):
    """A choice the group settled on (e.g. "we decided to use Postgres")."""

    memory_type: ClassVar[MemoryType] = MemoryType.DECISION


@dataclass(frozen=True)
class CommitmentMemory(ExtractedMemory):
    """An action somebody committed to, optionally with an owner and a deadline."""

    memory_type: ClassVar[MemoryType] = MemoryType.COMMITMENT

    owner: str | None = None
    due: str | None = None

    def to_dict(self) -> dict[str, object]:
        data = super().to_dict()
        data["owner"] = self.owner
        data["due"] = self.due
        return data


@dataclass(frozen=True)
class OpenLoopMemory(ExtractedMemory):
    """An unresolved thread that still needs attention (pending, follow-up, TBD)."""

    memory_type: ClassVar[MemoryType] = MemoryType.OPEN_LOOP


@dataclass(frozen=True)
class RiskMemory(ExtractedMemory):
    """A risk, concern, blocker, or dependency raised during the meeting."""

    memory_type: ClassVar[MemoryType] = MemoryType.RISK


@dataclass(frozen=True)
class AssumptionMemory(ExtractedMemory):
    """An assumption the discussion relied on (e.g. "assuming traffic stays flat")."""

    memory_type: ClassVar[MemoryType] = MemoryType.ASSUMPTION


@dataclass(frozen=True)
class QuestionMemory(ExtractedMemory):
    """An explicit question raised during the meeting."""

    memory_type: ClassVar[MemoryType] = MemoryType.QUESTION


@dataclass(frozen=True)
class FactMemory(ExtractedMemory):
    """An important factual statement (project, customer, metric, constraint...)."""

    memory_type: ClassVar[MemoryType] = MemoryType.FACT


# Order used when grouping/sorting memories for stable, readable output.
MEMORY_TYPE_ORDER: tuple[MemoryType, ...] = (
    MemoryType.DECISION,
    MemoryType.COMMITMENT,
    MemoryType.OPEN_LOOP,
    MemoryType.RISK,
    MemoryType.ASSUMPTION,
    MemoryType.QUESTION,
    MemoryType.FACT,
)


@dataclass(frozen=True)
class ExtractionResult:
    """The full set of memories extracted from a single meeting."""

    meeting_id: str
    memories: tuple[ExtractedMemory, ...] = field(default_factory=tuple)
    meeting_metadata: dict[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        """Total number of extracted memories."""
        return len(self.memories)

    def counts(self) -> dict[str, int]:
        """Number of memories per type, ordered by :data:`MEMORY_TYPE_ORDER`."""
        counter: Counter[MemoryType] = Counter(m.memory_type for m in self.memories)
        return {
            memory_type.value: counter.get(memory_type, 0)
            for memory_type in MEMORY_TYPE_ORDER
            if counter.get(memory_type, 0) > 0
        }

    def grouped(self) -> dict[str, list[ExtractedMemory]]:
        """Memories grouped by type, ordered by :data:`MEMORY_TYPE_ORDER`."""
        groups: dict[str, list[ExtractedMemory]] = {}
        for memory_type in MEMORY_TYPE_ORDER:
            items = [m for m in self.memories if m.memory_type is memory_type]
            if items:
                groups[memory_type.value] = items
        return groups

    def to_dict(self) -> dict[str, object]:
        """Serialise the result into JSON-compatible primitives."""
        return {
            "meeting_id": self.meeting_id,
            "meeting": self.meeting_metadata,
            "total": self.total,
            "counts": self.counts(),
            "memories": {
                memory_type: [memory.to_dict() for memory in items]
                for memory_type, items in self.grouped().items()
            },
            "warnings": list(self.warnings),
        }
