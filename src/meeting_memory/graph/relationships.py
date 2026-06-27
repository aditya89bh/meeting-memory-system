"""Deterministic relationship extraction for the memory graph.

Given a meeting, its memories, and the entities detected in them, this module
builds the *intra-meeting* edges: structural links (a memory was discussed in a
meeting, is owned by its speaker, a commitment is assigned to a person) and
semantic links derived from shared entities (a decision relates to a project, a
risk blocks a project, a fact references a customer, a question relates to a
decision, an assumption supports a decision). Cross-meeting and lineage edges are
added later by the builder, which has a global view. Everything here is rule
based and reproducible.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..storage import StoredMeeting, StoredMemory
from .entities import EntityExtraction
from .models import EntityType, GraphEdge, GraphNode, RelationshipType, slugify


def _person_id(name: str) -> str:
    return GraphNode.make_id(EntityType.PERSON, slugify(name))


def _entity_type_of(node_id: str) -> str:
    return node_id.split(":", 1)[0]


def meeting_relationships(
    meeting: StoredMeeting,
    memories: Sequence[StoredMemory],
    extraction: EntityExtraction,
) -> list[GraphEdge]:
    """Build every intra-meeting edge for one meeting."""
    created = meeting.created_at
    meeting_node = GraphNode.make_id(EntityType.MEETING, meeting.meeting_id)
    edges: list[GraphEdge] = []

    for participant in meeting.participants:
        edges.append(
            GraphEdge.create(
                meeting_node, RelationshipType.MENTIONS, _person_id(participant), created_at=created
            )
        )
    for entity_id in sorted(extraction.meeting_mentions):
        edges.append(
            GraphEdge.create(meeting_node, RelationshipType.MENTIONS, entity_id, created_at=created)
        )

    memory_nodes = {memory.memory_id: GraphNode.for_memory(memory).node_id for memory in memories}
    for memory in memories:
        node_id = memory_nodes[memory.memory_id]
        edges.append(
            GraphEdge.create(
                node_id, RelationshipType.DISCUSSED_IN, meeting_node, created_at=created
            )
        )
        if memory.speaker:
            edges.append(
                GraphEdge.create(
                    node_id,
                    RelationshipType.OWNED_BY,
                    _person_id(memory.speaker),
                    created_at=created,
                )
            )
        if memory.memory_type == "commitment":
            owner = memory.metadata.get("owner") or memory.speaker
            if owner:
                edges.append(
                    GraphEdge.create(
                        node_id,
                        RelationshipType.ASSIGNED_TO,
                        _person_id(owner),
                        created_at=created,
                    )
                )

        mentions = extraction.memory_mentions.get(memory.memory_id, frozenset())
        for entity_id in sorted(mentions):
            edges.append(
                GraphEdge.create(node_id, RelationshipType.MENTIONS, entity_id, created_at=created)
            )
            kind = _entity_type_of(entity_id)
            if memory.memory_type == "decision" and kind == EntityType.PROJECT.value:
                edges.append(
                    GraphEdge.create(
                        node_id, RelationshipType.RELATES_TO, entity_id, created_at=created
                    )
                )
            elif memory.memory_type == "risk" and kind == EntityType.PROJECT.value:
                edges.append(
                    GraphEdge.create(
                        node_id, RelationshipType.BLOCKS, entity_id, created_at=created
                    )
                )
            elif memory.memory_type == "fact" and kind == EntityType.CUSTOMER.value:
                edges.append(
                    GraphEdge.create(
                        node_id, RelationshipType.REFERENCES, entity_id, created_at=created
                    )
                )

        projects = sorted(e for e in mentions if _entity_type_of(e) == EntityType.PROJECT.value)
        technologies = sorted(
            e for e in mentions if _entity_type_of(e) == EntityType.TECHNOLOGY.value
        )
        for project_id in projects:
            for technology_id in technologies:
                edges.append(
                    GraphEdge.create(
                        project_id, RelationshipType.DEPENDS_ON, technology_id, created_at=created
                    )
                )

    edges.extend(_shared_entity_links(memories, memory_nodes, extraction, created))
    return edges


def _shared_entity_links(
    memories: Sequence[StoredMemory],
    memory_nodes: dict[str, str],
    extraction: EntityExtraction,
    created: str,
) -> list[GraphEdge]:
    """Link questions/assumptions to decisions that share a mentioned entity."""
    decisions = [m for m in memories if m.memory_type == "decision"]
    edges: list[GraphEdge] = []
    pairs = (
        ("question", RelationshipType.RELATES_TO),
        ("assumption", RelationshipType.SUPPORTS),
    )
    for memory_type, relationship in pairs:
        sources = [m for m in memories if m.memory_type == memory_type]
        for source in sources:
            source_entities = extraction.memory_mentions.get(source.memory_id, frozenset())
            if not source_entities:
                continue
            for decision in decisions:
                decision_entities = extraction.memory_mentions.get(decision.memory_id, frozenset())
                if source_entities & decision_entities:
                    edges.append(
                        GraphEdge.create(
                            memory_nodes[source.memory_id],
                            relationship,
                            memory_nodes[decision.memory_id],
                            created_at=created,
                        )
                    )
    return edges


__all__ = ["meeting_relationships"]
