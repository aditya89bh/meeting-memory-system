"""The deterministic retrieval engine.

:class:`MemoryRetriever` plans a query, selects candidate memories from the store
with strict AND semantics across every filter, orders them deterministically, and
paginates the result. Ranking, context assembly, and explanations are layered on
in their own modules and attached here.
"""

from __future__ import annotations

import dataclasses

from ..storage import MemoryStore, StoredMeeting, StoredMemory
from .context import ContextAssembler
from .explain import explain_match
from .models import (
    RankedMemory,
    RetrievalFilter,
    RetrievalQuery,
    RetrievalResult,
    RetrievalStats,
)
from .planner import PlannerVocabulary, QueryPlanner
from .ranking import RankingWeights, score_components, score_memory

_ORDER_RELEVANCE = "relevance"
_ORDER_CHRONOLOGICAL = "chronological"
_ORDER_REVERSE = "reverse-chronological"


class MemoryRetriever:
    """Search the persistent memory store deterministically."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        planner: QueryPlanner | None = None,
        weights: RankingWeights | None = None,
        assembler: ContextAssembler | None = None,
    ) -> None:
        self._store = store
        self._planner = planner or QueryPlanner()
        self._weights = weights or RankingWeights()
        self._assembler = assembler or ContextAssembler()

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """Plan, filter, rank, order, and paginate a retrieval query."""
        meetings = {meeting.meeting_id: meeting for meeting in self._store.list_meetings()}
        applied = self._planner.plan(query, self._vocabulary(meetings))
        candidates = self._candidates(applied, meetings)
        recency = _recency_map(candidates, meetings)
        ranked = [
            self._rank(memory, meetings.get(memory.meeting_id), applied, recency)
            for memory in candidates
        ]
        ranked = self._order(ranked, query.order)
        page = self._paginate(ranked, query.offset, query.limit)
        page = [self._enrich(item, applied, recency, query.context_size) for item in page]
        stats = RetrievalStats(
            candidates=len(ranked),
            returned=len(page),
            offset=query.offset,
            limit=query.limit,
        )
        return RetrievalResult(query=query, applied_filter=applied, ranked=tuple(page), stats=stats)

    # -- temporal retrieval ----------------------------------------------------

    def before(self, date: str, base: RetrievalQuery | None = None) -> RetrievalResult:
        """Memories from meetings on or before ``date``, oldest first."""
        query = base or RetrievalQuery()
        return self.retrieve(dataclasses.replace(query, date_to=date, order=_ORDER_CHRONOLOGICAL))

    def after(self, date: str, base: RetrievalQuery | None = None) -> RetrievalResult:
        """Memories from meetings on or after ``date``, oldest first."""
        query = base or RetrievalQuery()
        return self.retrieve(dataclasses.replace(query, date_from=date, order=_ORDER_CHRONOLOGICAL))

    def between(self, start: str, end: str, base: RetrievalQuery | None = None) -> RetrievalResult:
        """Memories from meetings between ``start`` and ``end`` (inclusive)."""
        query = base or RetrievalQuery()
        return self.retrieve(
            dataclasses.replace(query, date_from=start, date_to=end, order=_ORDER_CHRONOLOGICAL)
        )

    def latest(self, limit: int = 10, base: RetrievalQuery | None = None) -> RetrievalResult:
        """The most recent memories first."""
        query = base or RetrievalQuery()
        return self.retrieve(dataclasses.replace(query, limit=limit, order=_ORDER_REVERSE))

    def oldest(self, limit: int = 10, base: RetrievalQuery | None = None) -> RetrievalResult:
        """The earliest memories first."""
        query = base or RetrievalQuery()
        return self.retrieve(dataclasses.replace(query, limit=limit, order=_ORDER_CHRONOLOGICAL))

    def timeline(self, base: RetrievalQuery | None = None) -> RetrievalResult:
        """All matching memories in chronological order."""
        query = base or RetrievalQuery()
        return self.retrieve(dataclasses.replace(query, order=_ORDER_CHRONOLOGICAL))

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

    # -- ranking ---------------------------------------------------------------

    def _rank(
        self,
        memory: StoredMemory,
        meeting: StoredMeeting | None,
        applied: RetrievalFilter,
        recency: dict[str, float],
    ) -> RankedMemory:
        score = score_memory(
            memory,
            meeting,
            applied,
            recency=recency.get(memory.meeting_id, 1.0),
            weights=self._weights,
        )
        return RankedMemory(memory=memory, score=score, meeting=meeting)

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

    def _enrich(
        self,
        item: RankedMemory,
        applied: RetrievalFilter,
        recency: dict[str, float],
        context_size: int,
    ) -> RankedMemory:
        components = score_components(
            item.memory,
            item.meeting,
            applied,
            recency=recency.get(item.memory.meeting_id, 1.0),
        )
        explanation = explain_match(item.memory, item.meeting, applied, components, self._weights)
        context = self._assembler.assemble(item.memory, item.meeting, context_size)
        return dataclasses.replace(item, explanation=explanation, context=context)


def _recency_map(
    candidates: list[StoredMemory], meetings: dict[str, StoredMeeting]
) -> dict[str, float]:
    """Map each candidate meeting to a recency score in ``[0, 1]``.

    Dates are ranked by position among the distinct candidate dates (oldest 0.0,
    newest 1.0). Undated meetings score 0.0; if at most one distinct date exists,
    recency is neutral (1.0) so it does not skew ranking.
    """
    distinct: set[str] = set()
    for memory in candidates:
        meeting = meetings.get(memory.meeting_id)
        if meeting is not None and meeting.date:
            distinct.add(meeting.date)
    dates = sorted(distinct)
    if len(dates) <= 1:
        return {memory.meeting_id: 1.0 for memory in candidates}
    position = {date: index / (len(dates) - 1) for index, date in enumerate(dates)}
    recency: dict[str, float] = {}
    for memory in candidates:
        meeting = meetings.get(memory.meeting_id)
        date = meeting.date if meeting else None
        recency[memory.meeting_id] = position.get(date, 0.0) if date else 0.0
    return recency


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
