"""Cross-meeting linking for the organizational memory graph.

Entities (projects, customers, technologies, ...) are already shared nodes, so
repeating one across meetings connects those meetings automatically. This module
adds the remaining cross-meeting edges deterministically and *append-only* —
existing relationships are never removed or rewritten:

* repeated memory content (same content hash) is chained with ``CONNECTED_TO``;
* a commitment that shares an entity with an earlier risk/open loop ``RESOLVES``
  it;
* people who attend the same meeting are linked with ``CONNECTED_TO`` (one edge
  per shared meeting, so repeat collaborators accumulate edges).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from ..storage import StoredMemory
from .models import EntityType, GraphEdge, GraphNode, RelationshipType, slugify


@dataclass(frozen=True)
class MemoryRecord:
    """A memory plus the graph context needed for cross-meeting linking."""

    memory: StoredMemory
    node_id: str
    meeting_date: str
    entities: frozenset[str]


@dataclass(frozen=True)
class MeetingRecord:
    """A meeting's participants used for collaboration linking."""

    meeting_id: str
    meeting_date: str
    participants: tuple[str, ...]


def _person_id(name: str) -> str:
    return GraphNode.make_id(EntityType.PERSON, slugify(name))


def repeated_content_edges(records: Sequence[MemoryRecord]) -> list[GraphEdge]:
    """Chain memories that repeat the same content across different meetings."""
    by_hash: dict[str, list[MemoryRecord]] = {}
    for record in records:
        by_hash.setdefault(record.memory.content_hash, []).append(record)

    edges: list[GraphEdge] = []
    for content_hash in sorted(by_hash):
        group = sorted(
            by_hash[content_hash],
            key=lambda r: (r.meeting_date, r.memory.meeting_id, r.memory.memory_id),
        )
        meetings = {record.memory.meeting_id for record in group}
        if len(meetings) < 2:
            continue
        for earlier, later in pairwise(group):
            if earlier.memory.meeting_id == later.memory.meeting_id:
                continue
            edges.append(
                GraphEdge.create(
                    later.node_id,
                    RelationshipType.CONNECTED_TO,
                    earlier.node_id,
                    created_at=later.memory.created_at,
                    metadata={"reason": "repeated_content", "content_hash": content_hash},
                    discriminator="repeated_content",
                )
            )
    return edges


def resolves_edges(records: Sequence[MemoryRecord]) -> list[GraphEdge]:
    """Link commitments to earlier risks/open loops that share an entity."""
    commitments = [r for r in records if r.memory.memory_type == "commitment"]
    issues = [r for r in records if r.memory.memory_type in ("risk", "open_loop")]
    edges: list[GraphEdge] = []
    for commitment in sorted(commitments, key=lambda r: r.memory.memory_id):
        if not commitment.entities:
            continue
        for issue in sorted(issues, key=lambda r: r.memory.memory_id):
            if commitment.memory.memory_id == issue.memory.memory_id:
                continue
            if not (commitment.entities & issue.entities):
                continue
            if commitment.meeting_date < issue.meeting_date:
                continue
            edges.append(
                GraphEdge.create(
                    commitment.node_id,
                    RelationshipType.RESOLVES,
                    issue.node_id,
                    created_at=commitment.memory.created_at,
                )
            )
    return edges


def collaboration_edges(meetings: Sequence[MeetingRecord]) -> list[GraphEdge]:
    """Link co-participants of each meeting (one edge per shared meeting)."""
    edges: list[GraphEdge] = []
    for meeting in meetings:
        people = sorted(set(meeting.participants))
        for index, first in enumerate(people):
            for second in people[index + 1 :]:
                edges.append(
                    GraphEdge.create(
                        _person_id(first),
                        RelationshipType.CONNECTED_TO,
                        _person_id(second),
                        metadata={"meeting_id": meeting.meeting_id},
                        discriminator=meeting.meeting_id,
                    )
                )
    return edges


def cross_meeting_edges(
    records: Sequence[MemoryRecord], meetings: Sequence[MeetingRecord]
) -> list[GraphEdge]:
    """Build every cross-meeting edge from the collected records."""
    edges: list[GraphEdge] = []
    edges.extend(repeated_content_edges(records))
    edges.extend(resolves_edges(records))
    edges.extend(collaboration_edges(meetings))
    return edges


__all__ = [
    "MeetingRecord",
    "MemoryRecord",
    "collaboration_edges",
    "cross_meeting_edges",
    "repeated_content_edges",
    "resolves_edges",
]
