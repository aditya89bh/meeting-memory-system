"""Typed models for the deterministic retrieval engine.

These records describe a retrieval request (`RetrievalQuery`), the executable
filter a planner derives from it (`RetrievalFilter`), and the structured answer
(`RetrievalResult` made of `RankedMemory` items, each with a `ContextWindow` and
a `RetrievalExplanation`). Everything is immutable and JSON-serialisable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..storage import MemoryQuery, MemoryStatus, StoredMeeting, StoredMemory


@dataclass(frozen=True)
class RetrievalQuery:
    """A high-level retrieval request combining free text and structured filters."""

    text: str | None = None
    meeting_ids: frozenset[str] = frozenset()
    speakers: frozenset[str] = frozenset()
    memory_types: frozenset[str] = frozenset()
    statuses: frozenset[MemoryStatus] = frozenset()
    participants: frozenset[str] = frozenset()
    months: frozenset[int] = frozenset()
    min_confidence: float | None = None
    max_confidence: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int | None = None
    offset: int = 0
    context_size: int = 1
    order: str = "relevance"

    def to_dict(self) -> dict[str, object]:
        """Serialise the query into JSON-compatible primitives."""
        return {
            "text": self.text,
            "meeting_ids": sorted(self.meeting_ids),
            "speakers": sorted(self.speakers),
            "memory_types": sorted(self.memory_types),
            "statuses": sorted(status.value for status in self.statuses),
            "participants": sorted(self.participants),
            "months": sorted(self.months),
            "min_confidence": self.min_confidence,
            "max_confidence": self.max_confidence,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "limit": self.limit,
            "offset": self.offset,
            "context_size": self.context_size,
            "order": self.order,
        }


@dataclass(frozen=True)
class RetrievalFilter:
    """An executable filter produced by the query planner.

    Structured fields map onto the storage layer; ``terms``/``phrase`` drive
    keyword matching and exact-phrase ranking in the engine.
    """

    terms: tuple[str, ...] = ()
    phrase: str | None = None
    memory_types: frozenset[str] = frozenset()
    statuses: frozenset[MemoryStatus] = frozenset()
    speakers: frozenset[str] = frozenset()
    meeting_ids: frozenset[str] = frozenset()
    participants: frozenset[str] = frozenset()
    months: frozenset[int] = frozenset()
    min_confidence: float | None = None
    max_confidence: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int | None = None
    offset: int = 0

    @property
    def phrase_core(self) -> str | None:
        """The contiguous keyword phrase (>= 2 terms) used for exact-phrase bonus."""
        return " ".join(self.terms) if len(self.terms) >= 2 else None

    def to_storage_query(self) -> MemoryQuery:
        """Translate the structured part of the filter into a storage query."""
        return MemoryQuery(
            memory_types=self.memory_types or None,
            speakers=self.speakers or None,
            meeting_ids=self.meeting_ids or None,
            statuses=self.statuses or None,
            min_confidence=self.min_confidence,
            max_confidence=self.max_confidence,
            date_from=self.date_from,
            date_to=self.date_to,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialise the filter into JSON-compatible primitives."""
        return {
            "terms": list(self.terms),
            "phrase": self.phrase,
            "memory_types": sorted(self.memory_types),
            "statuses": sorted(status.value for status in self.statuses),
            "speakers": sorted(self.speakers),
            "meeting_ids": sorted(self.meeting_ids),
            "participants": sorted(self.participants),
            "months": sorted(self.months),
            "min_confidence": self.min_confidence,
            "max_confidence": self.max_confidence,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(frozen=True)
class ExplanationReason:
    """A single, human-readable reason a memory was returned."""

    factor: str
    detail: str
    contribution: float = 0.0

    def to_dict(self) -> dict[str, object]:
        """Serialise the reason into JSON-compatible primitives."""
        return {
            "factor": self.factor,
            "detail": self.detail,
            "contribution": round(self.contribution, 4),
        }


@dataclass(frozen=True)
class RetrievalExplanation:
    """Why a memory matched: an ordered list of concrete reasons."""

    reasons: tuple[ExplanationReason, ...] = ()

    def lines(self) -> list[str]:
        """Render the explanation as checkmark lines for CLI output."""
        return [f"\u2713 {reason.detail}" for reason in self.reasons]

    def to_dict(self) -> dict[str, object]:
        """Serialise the explanation into JSON-compatible primitives."""
        return {"reasons": [reason.to_dict() for reason in self.reasons]}


@dataclass(frozen=True)
class ContextUtterance:
    """One utterance in a context window."""

    index: int
    speaker: str | None
    text: str
    is_match: bool = False

    def to_dict(self) -> dict[str, object]:
        """Serialise the context utterance into JSON-compatible primitives."""
        return {
            "index": self.index,
            "speaker": self.speaker,
            "text": self.text,
            "is_match": self.is_match,
        }


@dataclass(frozen=True)
class ContextWindow:
    """Surrounding utterances around the memory's source utterance."""

    before: tuple[ContextUtterance, ...] = ()
    target: ContextUtterance | None = None
    after: tuple[ContextUtterance, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialise the context window into JSON-compatible primitives."""
        return {
            "before": [utterance.to_dict() for utterance in self.before],
            "target": self.target.to_dict() if self.target else None,
            "after": [utterance.to_dict() for utterance in self.after],
        }


@dataclass(frozen=True)
class RankedMemory:
    """A retrieved memory with its score, explanation, and context."""

    memory: StoredMemory
    score: float
    explanation: RetrievalExplanation | None = None
    context: ContextWindow | None = None
    meeting: StoredMeeting | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the ranked memory into JSON-compatible primitives."""
        payload: dict[str, object] = {
            "memory": self.memory.to_dict(),
            "score": round(self.score, 4),
        }
        if self.explanation is not None:
            payload["explanation"] = self.explanation.to_dict()
        if self.context is not None:
            payload["context"] = self.context.to_dict()
        if self.meeting is not None:
            payload["meeting"] = {
                "meeting_id": self.meeting.meeting_id,
                "title": self.meeting.title,
                "date": self.meeting.date,
            }
        return payload


@dataclass(frozen=True)
class RetrievalStats:
    """Counts describing a retrieval run."""

    candidates: int
    returned: int
    offset: int
    limit: int | None

    def to_dict(self) -> dict[str, object]:
        """Serialise the stats into JSON-compatible primitives."""
        return {
            "candidates": self.candidates,
            "returned": self.returned,
            "offset": self.offset,
            "limit": self.limit,
        }


@dataclass(frozen=True)
class RetrievalResult:
    """The full answer to a retrieval query."""

    query: RetrievalQuery
    applied_filter: RetrievalFilter
    ranked: tuple[RankedMemory, ...] = ()
    stats: RetrievalStats = field(default_factory=lambda: RetrievalStats(0, 0, 0, None))

    def to_dict(self) -> dict[str, object]:
        """Serialise the result into JSON-compatible primitives."""
        return {
            "query": self.query.to_dict(),
            "filter": self.applied_filter.to_dict(),
            "stats": self.stats.to_dict(),
            "results": [ranked.to_dict() for ranked in self.ranked],
        }
