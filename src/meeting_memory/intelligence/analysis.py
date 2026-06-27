"""Shared deterministic analysis helpers used by the domain providers.

These helpers turn stored memories into the building blocks every analysis needs
— content-recurrence groups, supersession chains, severity scaling, evidence,
and stable insight ids — without any randomness or wall-clock dependence.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..graph import EntityType, RelationshipType, slugify
from ..storage import MemoryStatus, StoredMemory
from .context import AnalysisContext, owner_of
from .models import InsightEvidence, InsightSeverity, PersonMetrics, ProjectMetrics


def content_groups(memories: list[StoredMemory]) -> dict[str, list[StoredMemory]]:
    """Group memories by content hash, preserving first-seen order."""
    groups: dict[str, list[StoredMemory]] = defaultdict(list)
    for memory in memories:
        groups[memory.content_hash].append(memory)
    return dict(groups)


def recurring_groups(memories: list[StoredMemory]) -> dict[str, list[StoredMemory]]:
    """Return content groups that span more than one distinct meeting.

    Sorted by descending recurrence (then by hash) for deterministic output.
    """
    groups = content_groups(memories)
    recurring = {
        digest: items
        for digest, items in groups.items()
        if len({item.meeting_id for item in items}) > 1
    }
    return dict(
        sorted(
            recurring.items(),
            key=lambda kv: (-len({m.meeting_id for m in kv[1]}), kv[0]),
        )
    )


def supersession_chains(
    memories: list[StoredMemory], index: dict[str, StoredMemory]
) -> list[list[StoredMemory]]:
    """Return supersession chains ordered oldest-to-newest.

    ``memory.superseded_by`` points at the newer memory that replaced it, so each
    chain follows those pointers from the oldest decision to the latest one.
    """
    successor = {m.memory_id: m.superseded_by for m in memories if m.superseded_by}
    targets = set(successor.values())
    starts = sorted(
        (mid for mid in successor if mid not in targets),
        key=lambda mid: (index[mid].created_at, mid),
    )
    chains: list[list[StoredMemory]] = []
    for start in starts:
        chain: list[StoredMemory] = []
        current: str | None = start
        seen: set[str] = set()
        while current is not None and current in index and current not in seen:
            seen.add(current)
            chain.append(index[current])
            current = successor.get(current)
        if len(chain) > 1:
            chains.append(chain)
    return chains


def days_between(start: str, end: str) -> int:
    """Whole days between two ``YYYY-MM-DD`` dates (0 if either is unparsable)."""
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def chain_span_days(chain: list[StoredMemory], context: AnalysisContext) -> int:
    """Calendar days a supersession/recurrence chain spans across meetings."""
    dates = sorted(d for d in (context.memory_date(m) for m in chain) if d)
    if len(dates) < 2:
        return 0
    return days_between(dates[0], dates[-1])


def scale_severity(value: int, medium: int, high: int, critical: int) -> InsightSeverity:
    """Map a count onto a severity using ascending thresholds."""
    if value >= critical:
        return InsightSeverity.CRITICAL
    if value >= high:
        return InsightSeverity.HIGH
    if value >= medium:
        return InsightSeverity.MEDIUM
    return InsightSeverity.LOW


def memory_evidence(
    memories: list[StoredMemory], description: str, *, value: float | None = None
) -> InsightEvidence:
    """Build an :class:`InsightEvidence` referencing the given memories."""
    return InsightEvidence(
        description=description,
        memory_ids=tuple(m.memory_id for m in memories),
        meeting_ids=tuple(dict.fromkeys(m.meeting_id for m in memories)),
        value=value,
    )


def insight_id(*parts: str) -> str:
    """Compose a deterministic, slugified insight id from its parts."""
    return "-".join(slugify(part) for part in parts if part)


def top_counter(counts: dict[str, int]) -> tuple[str | None, int]:
    """Return the highest-count key (ties broken alphabetically) and its count."""
    if not counts:
        return None, 0
    name = sorted(counts, key=lambda key: (-counts[key], key))[0]
    return name, counts[name]


def project_metrics(context: AnalysisContext) -> list[ProjectMetrics]:
    """Per-project risk/decision/meeting/blocker counts from the graph.

    Returns an empty list when no graph is attached to ``context``.
    """
    graph = context.graph
    if graph is None:
        return []
    rows: list[ProjectMetrics] = []
    for node in graph.list_nodes(node_types=frozenset({EntityType.PROJECT})):
        risk_count = decision_count = meeting_count = blocker_count = 0
        for edge in graph.incoming(node.node_id):
            if edge.relationship is RelationshipType.BLOCKS:
                blocker_count += 1
            source = graph.get_node(edge.source_id) if graph.has_node(edge.source_id) else None
            if source is None:
                continue
            if source.node_type is EntityType.RISK:
                risk_count += 1
            elif source.node_type is EntityType.DECISION:
                decision_count += 1
            elif source.node_type is EntityType.MEETING:
                meeting_count += 1
        rows.append(
            ProjectMetrics(
                project_id=node.node_id,
                name=node.label,
                risk_count=risk_count,
                decision_count=decision_count,
                meeting_count=meeting_count,
                blocker_count=blocker_count,
            )
        )
    return rows


def person_metrics(context: AnalysisContext) -> list[PersonMetrics]:
    """Per-person commitment, decision, and attendance counts."""
    open_commit: dict[str, int] = {}
    total_commit: dict[str, int] = {}
    decisions: dict[str, int] = {}
    attended: dict[str, int] = {}
    for meeting in context.meetings:
        for person in set(meeting.participants):
            attended[person] = attended.get(person, 0) + 1
    for memory in context.memories:
        if memory.memory_type == "commitment":
            owner = owner_of(memory)
            if owner:
                total_commit[owner] = total_commit.get(owner, 0) + 1
                if memory.status is MemoryStatus.ACTIVE:
                    open_commit[owner] = open_commit.get(owner, 0) + 1
        elif memory.memory_type == "decision" and memory.speaker:
            decisions[memory.speaker] = decisions.get(memory.speaker, 0) + 1

    names = sorted(set(open_commit) | set(total_commit) | set(decisions) | set(attended))
    return [
        PersonMetrics(
            name=name,
            open_commitments=open_commit.get(name, 0),
            total_commitments=total_commit.get(name, 0),
            decisions_owned=decisions.get(name, 0),
            meetings_attended=attended.get(name, 0),
        )
        for name in names
    ]


__all__ = [
    "chain_span_days",
    "content_groups",
    "days_between",
    "insight_id",
    "memory_evidence",
    "person_metrics",
    "project_metrics",
    "recurring_groups",
    "scale_severity",
    "supersession_chains",
    "top_counter",
]
