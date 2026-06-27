"""Analysis context shared by every intelligence provider.

The context is built once from the storage and graph layers and then passed to
every provider, so analyses never touch the database directly and always see the
same, already-filtered view of organizational memory. A deterministic
``reference_date`` (the latest meeting date by default) replaces wall-clock time
so age- and overdue-based analyses are reproducible.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass

from ..graph import EntityType, GraphNode, GraphStore
from ..storage import MemoryStatus, StoredMeeting, StoredMemory


@dataclass(frozen=True)
class AnalysisFilters:
    """Optional filters narrowing the analysed slice of memory."""

    project: str | None = None
    person: str | None = None
    meetings: frozenset[str] = frozenset()
    memory_types: frozenset[str] = frozenset()

    def to_dict(self) -> dict[str, object]:
        """Serialise the filters into JSON-compatible primitives."""
        return {
            "project": self.project,
            "person": self.person,
            "meetings": sorted(self.meetings),
            "memory_types": sorted(self.memory_types),
        }


@dataclass(frozen=True)
class AnalysisContext:
    """A deterministic, pre-filtered view of organizational memory."""

    memories: tuple[StoredMemory, ...]
    meetings: tuple[StoredMeeting, ...]
    reference_date: str
    filters: AnalysisFilters
    graph: GraphStore | None = None

    def by_type(self, *memory_types: str) -> builtins.list[StoredMemory]:
        """Return memories of the given type(s), in context order."""
        wanted = set(memory_types)
        return [memory for memory in self.memories if memory.memory_type in wanted]

    def meeting(self, meeting_id: str) -> StoredMeeting | None:
        """Return the meeting with ``meeting_id`` if present."""
        for meeting in self.meetings:
            if meeting.meeting_id == meeting_id:
                return meeting
        return None

    def meeting_date(self, meeting_id: str) -> str:
        """Return the date of a meeting, or ``''`` when unknown."""
        meeting = self.meeting(meeting_id)
        return (meeting.date or "") if meeting is not None else ""

    def memory_date(self, memory: StoredMemory) -> str:
        """Return the meeting date a memory belongs to (``''`` if unknown)."""
        return self.meeting_date(memory.meeting_id)

    @property
    def span_days(self) -> int:
        """Calendar days between the earliest and latest meeting date."""
        dates = sorted(meeting.date for meeting in self.meetings if meeting.date)
        if len(dates) < 2:
            return 0
        return _days_between(dates[0], dates[-1])


def _days_between(start: str, end: str) -> int:
    """Whole days between two ``YYYY-MM-DD`` dates (0 if either is unparsable)."""
    from datetime import date

    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def owner_of(memory: StoredMemory) -> str | None:
    """Return the responsible person for a memory (commitment owner or speaker)."""
    return memory.metadata.get("owner") or memory.speaker


def _project_memory_ids(graph: GraphStore, project: str) -> set[str]:
    """Return memory ref-ids linked to a project node via the graph."""
    node_id = GraphNode.make_id(EntityType.PROJECT, _slug(project))
    if not graph.has_node(node_id):
        return set()
    linked: set[str] = set()
    for edge in graph.incoming(node_id):
        source = graph.get_node(edge.source_id) if graph.has_node(edge.source_id) else None
        if source is not None and source.node_type is not EntityType.MEETING:
            linked.add(source.ref_id)
    return linked


def _slug(name: str) -> str:
    from ..graph import slugify

    return slugify(name)


def build_context(
    memories: builtins.list[StoredMemory],
    meetings: builtins.list[StoredMeeting],
    *,
    filters: AnalysisFilters | None = None,
    graph: GraphStore | None = None,
    reference_date: str | None = None,
) -> AnalysisContext:
    """Filter ``memories``/``meetings`` and assemble an :class:`AnalysisContext`."""
    active_filters = filters or AnalysisFilters()

    selected_meetings = list(meetings)
    if active_filters.meetings:
        wanted = active_filters.meetings
        selected_meetings = [m for m in selected_meetings if m.meeting_id in wanted]
    selected_meetings.sort(key=lambda m: (m.date or "", m.created_at, m.meeting_id))
    meeting_ids = {meeting.meeting_id for meeting in selected_meetings}

    project_ids: set[str] | None = None
    if active_filters.project and graph is not None:
        project_ids = _project_memory_ids(graph, active_filters.project)

    selected: list[StoredMemory] = []
    for memory in memories:
        if memory.status is MemoryStatus.DELETED:
            continue
        if memory.meeting_id not in meeting_ids:
            continue
        if active_filters.memory_types and memory.memory_type not in active_filters.memory_types:
            continue
        if active_filters.person and owner_of(memory) != active_filters.person:
            continue
        if project_ids is not None and memory.memory_id not in project_ids:
            continue
        selected.append(memory)
    selected.sort(key=lambda m: (m.created_at, m.memory_id))

    resolved_reference = reference_date or _latest_date(selected_meetings) or ""
    return AnalysisContext(
        memories=tuple(selected),
        meetings=tuple(selected_meetings),
        reference_date=resolved_reference,
        filters=active_filters,
        graph=graph,
    )


def _latest_date(meetings: builtins.list[StoredMeeting]) -> str | None:
    dates = sorted(meeting.date for meeting in meetings if meeting.date)
    return dates[-1] if dates else None


__all__ = [
    "AnalysisContext",
    "AnalysisFilters",
    "build_context",
    "owner_of",
]
