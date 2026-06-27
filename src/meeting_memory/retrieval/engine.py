"""The deterministic retrieval engine.

:class:`MemoryRetriever` plans a query, selects candidate memories from the store
with strict AND semantics across every filter, orders them deterministically, and
paginates the result. Ranking, context assembly, and explanations are layered on
in their own modules and attached here.
"""

from __future__ import annotations

from ..storage import MemoryStore, StoredMeeting, StoredMemory
from .models import (
    RankedMemory,
    RetrievalFilter,
    RetrievalQuery,
    RetrievalResult,
    RetrievalStats,
)
from .planner import PlannerVocabulary, QueryPlanner

_ORDER_RELEVANCE = "relevance"
_ORDER_CHRONOLOGICAL = "chronological"
_ORDER_REVERSE = "reverse-chronological"


class MemoryRetriever:
    """Search the persistent memory store deterministically."""

    def __init__(self, store: MemoryStore, *, planner: QueryPlanner | None = None) -> None:
        self._store = store
        self._planner = planner or QueryPlanner()

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Plan, filter, rank, order, and paginate a retrieval query."""
        meetings = {meeting.meeting_id: meeting for meeting in self._store.list_meetings()}
        applied = self._planner.plan(query, self._vocabulary(meetings))
        candidates = self._candidates(applied, meetings)
        ranked = [self._rank(memory, meetings.get(memory.meeting_id)) for memory in candidates]
        ranked = self._order(ranked, query.order)
        page = self._paginate(ranked, query.offset, query.limit)
        stats = RetrievalStats(
            candidates=len(ranked),
            returned=len(page),
            offset=query.offset,
            limit=query.limit,
        )
        return RetrievalResult(query=query, applied_filter=applied, ranked=tuple(page), stats=stats)

    # -- candidate selection ---------------------------------------------------

    def _vocabulary(self, meetings: dict[str, StoredMeeting]) -> PlannerVocabulary:
        participants: set[str] = set()
        for meeting in meetings.values():
            participants.update(meeting.participants)
        speakers = {memory.speaker for memory in self._store.list() if memory.speaker}
        return PlannerVocabulary(frozenset(speakers), frozenset(participants))

    def _candidates(
        self, applied: RetrievalFilter, meetings: dict[str, StoredMeeting]
    ) -> list[StoredMemory]:
        rows = self._store.query(applied.to_storage_query())
        selected: list[StoredMemory] = []
        for memory in rows:
            meeting = meetings.get(memory.meeting_id)
            if not _matches_terms(memory, meeting, applied.terms):
                continue
            if applied.participants and not _matches_participants(meeting, applied.participants):
                continue
            if applied.months and not _matches_months(meeting, applied.months):
                continue
            selected.append(memory)
        return selected

    # -- ranking (deterministic base; enriched by the ranking module) ----------

    def _rank(self, memory: StoredMemory, meeting: StoredMeeting | None) -> RankedMemory:
        return RankedMemory(memory=memory, score=memory.confidence, meeting=meeting)

    # -- ordering and pagination -----------------------------------------------

    def _order(self, ranked: list[RankedMemory], order: str) -> list[RankedMemory]:
        items = list(ranked)
        if order == _ORDER_CHRONOLOGICAL:
            items.sort(key=lambda item: item.memory.memory_id)
            items.sort(key=lambda item: item.memory.utterance_index)
            items.sort(key=_meeting_date)
            return items
        if order == _ORDER_REVERSE:
            items.sort(key=lambda item: item.memory.memory_id)
            items.sort(key=lambda item: item.memory.created_at, reverse=True)
            items.sort(key=_meeting_date, reverse=True)
            return items
        # Default: relevance — score desc, then most recent, then stable id.
        items.sort(key=lambda item: item.memory.memory_id)
        items.sort(key=lambda item: item.memory.created_at, reverse=True)
        items.sort(key=_meeting_date, reverse=True)
        items.sort(key=lambda item: item.score, reverse=True)
        return items

    def _paginate(
        self, ranked: list[RankedMemory], offset: int, limit: int | None
    ) -> list[RankedMemory]:
        if limit is None:
            return ranked[offset:]
        return ranked[offset : offset + limit]


def _searchable(memory: StoredMemory, meeting: StoredMeeting | None) -> str:
    parts = [memory.text, memory.speaker or "", *memory.metadata.values()]
    if meeting is not None:
        parts.append(meeting.title or "")
        parts.extend(meeting.participants)
    return " ".join(parts).lower()


def _matches_terms(
    memory: StoredMemory, meeting: StoredMeeting | None, terms: tuple[str, ...]
) -> bool:
    if not terms:
        return True
    haystack = _searchable(memory, meeting)
    return all(term in haystack for term in terms)


def _matches_participants(meeting: StoredMeeting | None, participants: frozenset[str]) -> bool:
    if meeting is None:
        return False
    present = set(meeting.participants)
    return participants <= present


def _matches_months(meeting: StoredMeeting | None, months: frozenset[int]) -> bool:
    if meeting is None or not meeting.date:
        return False
    return int(meeting.date[5:7]) in months


def _meeting_date(item: RankedMemory) -> str:
    if item.meeting is not None and item.meeting.date:
        return item.meeting.date
    return ""
