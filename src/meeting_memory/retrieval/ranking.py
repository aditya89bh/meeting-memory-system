"""Deterministic ranking model.

Each candidate memory is scored in ``[0.0, 1.0]`` as a fixed weighted sum of six
transparent components: keyword/text match, exact-phrase match, confidence,
meeting recency, lifecycle status, and meeting relevance. There is no learning or
randomness, so the same inputs always yield the same score. Ties are broken by
the engine using stable, deterministic ordering.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..storage import MemoryStatus, StoredMeeting, StoredMemory
from .models import RetrievalFilter

_STATUS_WEIGHT: dict[MemoryStatus, float] = {
    MemoryStatus.ACTIVE: 1.0,
    MemoryStatus.RESOLVED: 0.7,
    MemoryStatus.ARCHIVED: 0.5,
    MemoryStatus.SUPERSEDED: 0.3,
    MemoryStatus.DELETED: 0.1,
}


@dataclass(frozen=True)
class RankingWeights:
    """Relative importance of each scoring component (sums to 1.0)."""

    text: float = 0.30
    phrase: float = 0.15
    confidence: float = 0.20
    recency: float = 0.15
    status: float = 0.10
    meeting: float = 0.10


DEFAULT_WEIGHTS = RankingWeights()


@dataclass(frozen=True)
class ScoreComponents:
    """The individual, bounded components behind a memory's score."""

    text: float
    phrase: float
    confidence: float
    recency: float
    status: float
    meeting: float

    def total(self, weights: RankingWeights = DEFAULT_WEIGHTS) -> float:
        """Combine the components into a single clamped score."""
        raw = (
            weights.text * self.text
            + weights.phrase * self.phrase
            + weights.confidence * self.confidence
            + weights.recency * self.recency
            + weights.status * self.status
            + weights.meeting * self.meeting
        )
        return _clamp(raw)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def status_score(status: MemoryStatus) -> float:
    """Score a lifecycle status (active is most relevant)."""
    return _STATUS_WEIGHT.get(status, 0.1)


def text_score(memory: StoredMemory, terms: tuple[str, ...]) -> float:
    """Fraction of query terms found in the memory body (text/speaker/metadata)."""
    if not terms:
        return 1.0
    body = " ".join([memory.text, memory.speaker or "", *memory.metadata.values()]).lower()
    found = sum(1 for term in terms if term in body)
    return found / len(terms)


def meeting_score(meeting: StoredMeeting | None, terms: tuple[str, ...]) -> float:
    """Fraction of query terms found in the meeting title/participants."""
    if not terms:
        return 1.0
    if meeting is None:
        return 0.0
    body = " ".join([meeting.title or "", *meeting.participants]).lower()
    found = sum(1 for term in terms if term in body)
    return found / len(terms)


def phrase_score(memory: StoredMemory, phrase_core: str | None) -> float:
    """1.0 when the exact multi-term phrase appears in the memory text."""
    if phrase_core is None:
        return 1.0
    return 1.0 if phrase_core in memory.text.lower() else 0.0


def score_components(
    memory: StoredMemory,
    meeting: StoredMeeting | None,
    applied: RetrievalFilter,
    *,
    recency: float,
) -> ScoreComponents:
    """Compute every scoring component for a memory."""
    return ScoreComponents(
        text=text_score(memory, applied.terms),
        phrase=phrase_score(memory, applied.phrase_core),
        confidence=_clamp(memory.confidence),
        recency=_clamp(recency),
        status=status_score(memory.status),
        meeting=meeting_score(meeting, applied.terms),
    )


def score_memory(
    memory: StoredMemory,
    meeting: StoredMeeting | None,
    applied: RetrievalFilter,
    *,
    recency: float,
    weights: RankingWeights = DEFAULT_WEIGHTS,
) -> float:
    """Return the final ``[0, 1]`` relevance score for a memory."""
    return score_components(memory, meeting, applied, recency=recency).total(weights)
