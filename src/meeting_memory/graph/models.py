"""Typed models for the Organizational Memory Graph.

The graph links meetings, memories, people, and extracted entities (projects,
customers, technologies, ...) with typed, directed edges. Every model is an
immutable, JSON-serialisable value object, and node/edge identifiers are
*deterministic* functions of their content so rebuilding the graph from the same
store always yields the same ids — which is what makes cross-meeting linking and
idempotent persistence work.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum

from ..storage import StoredMeeting, StoredMemory

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class EntityType(str, Enum):
    """The kind of thing a graph node represents."""

    MEETING = "meeting"
    MEMORY = "memory"
    PERSON = "person"
    PROJECT = "project"
    CUSTOMER = "customer"
    TECHNOLOGY = "technology"
    TEAM = "team"
    VENDOR = "vendor"
    DOCUMENT = "document"
    DECISION = "decision"
    COMMITMENT = "commitment"
    RISK = "risk"
    QUESTION = "question"
    ASSUMPTION = "assumption"
    FACT = "fact"

    def __str__(self) -> str:
        return self.value


class RelationshipType(str, Enum):
    """The kind of directed relationship a graph edge represents."""

    MENTIONS = "mentions"
    ASSIGNED_TO = "assigned_to"
    RELATES_TO = "relates_to"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"
    RESOLVES = "resolves"
    BLOCKS = "blocks"
    SUPPORTS = "supports"
    REFERENCES = "references"
    DISCUSSED_IN = "discussed_in"
    OWNED_BY = "owned_by"
    CONNECTED_TO = "connected_to"

    def __str__(self) -> str:
        return self.value


# Memory primitive type (string) -> graph node type. ``open_loop`` has no
# dedicated node type, so it maps to the generic MEMORY node.
_MEMORY_TYPE_TO_ENTITY: dict[str, EntityType] = {
    "decision": EntityType.DECISION,
    "commitment": EntityType.COMMITMENT,
    "risk": EntityType.RISK,
    "question": EntityType.QUESTION,
    "assumption": EntityType.ASSUMPTION,
    "fact": EntityType.FACT,
    "open_loop": EntityType.MEMORY,
}


def slugify(name: str) -> str:
    """Turn a free-text name into a stable, lowercase identifier fragment."""
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "unknown"


@dataclass(frozen=True)
class GraphRelationship:
    """Descriptor for a relationship type: its label and whether it is directed."""

    relationship: RelationshipType
    label: str
    directed: bool = True

    def to_dict(self) -> dict[str, object]:
        """Serialise the relationship descriptor into JSON-compatible primitives."""
        return {
            "relationship": self.relationship.value,
            "label": self.label,
            "directed": self.directed,
        }


# Registry describing every relationship type (used for export labels).
RELATIONSHIP_REGISTRY: dict[RelationshipType, GraphRelationship] = {
    RelationshipType.MENTIONS: GraphRelationship(RelationshipType.MENTIONS, "mentions"),
    RelationshipType.ASSIGNED_TO: GraphRelationship(RelationshipType.ASSIGNED_TO, "assigned to"),
    RelationshipType.RELATES_TO: GraphRelationship(RelationshipType.RELATES_TO, "relates to"),
    RelationshipType.DEPENDS_ON: GraphRelationship(RelationshipType.DEPENDS_ON, "depends on"),
    RelationshipType.SUPERSEDES: GraphRelationship(RelationshipType.SUPERSEDES, "supersedes"),
    RelationshipType.RESOLVES: GraphRelationship(RelationshipType.RESOLVES, "resolves"),
    RelationshipType.BLOCKS: GraphRelationship(RelationshipType.BLOCKS, "blocks"),
    RelationshipType.SUPPORTS: GraphRelationship(RelationshipType.SUPPORTS, "supports"),
    RelationshipType.REFERENCES: GraphRelationship(RelationshipType.REFERENCES, "references"),
    RelationshipType.DISCUSSED_IN: GraphRelationship(RelationshipType.DISCUSSED_IN, "discussed in"),
    RelationshipType.OWNED_BY: GraphRelationship(RelationshipType.OWNED_BY, "owned by"),
    RelationshipType.CONNECTED_TO: GraphRelationship(
        RelationshipType.CONNECTED_TO, "connected to", directed=False
    ),
}


@dataclass(frozen=True)
class GraphNode:
    """A single node in the organizational memory graph."""

    node_id: str
    node_type: EntityType
    label: str
    ref_id: str
    created_at: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def make_id(node_type: EntityType, ref: str) -> str:
        """Compose a deterministic node id from a type and reference."""
        return f"{node_type.value}:{ref}"

    @classmethod
    def for_meeting(cls, meeting: StoredMeeting, *, created_at: str = "") -> GraphNode:
        """Build the node representing a meeting."""
        metadata: dict[str, str] = {}
        if meeting.date:
            metadata["date"] = meeting.date
        return cls(
            node_id=cls.make_id(EntityType.MEETING, meeting.meeting_id),
            node_type=EntityType.MEETING,
            label=meeting.title or meeting.meeting_id,
            ref_id=meeting.meeting_id,
            created_at=created_at or meeting.created_at,
            metadata=metadata,
        )

    @classmethod
    def for_memory(cls, memory: StoredMemory, *, created_at: str = "") -> GraphNode:
        """Build the node representing an extracted memory."""
        node_type = _MEMORY_TYPE_TO_ENTITY.get(memory.memory_type, EntityType.MEMORY)
        return cls(
            node_id=cls.make_id(node_type, memory.memory_id),
            node_type=node_type,
            label=memory.text,
            ref_id=memory.memory_id,
            created_at=created_at or memory.created_at,
            metadata={"status": memory.status.value, "meeting_id": memory.meeting_id},
        )

    @classmethod
    def for_person(cls, name: str, *, created_at: str = "") -> GraphNode:
        """Build the node representing a person."""
        ref = slugify(name)
        return cls(
            node_id=cls.make_id(EntityType.PERSON, ref),
            node_type=EntityType.PERSON,
            label=name,
            ref_id=ref,
            created_at=created_at,
        )

    @classmethod
    def for_entity(cls, node_type: EntityType, name: str, *, created_at: str = "") -> GraphNode:
        """Build the node representing an extracted entity (project, customer, ...)."""
        ref = slugify(name)
        return cls(
            node_id=cls.make_id(node_type, ref),
            node_type=node_type,
            label=name,
            ref_id=ref,
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialise the node into JSON-compatible primitives."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "ref_id": self.ref_id,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GraphEdge:
    """A single directed, typed edge between two nodes."""

    edge_id: str
    source_id: str
    target_id: str
    relationship: RelationshipType
    created_at: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def make_id(
        source_id: str, relationship: RelationshipType, target_id: str, discriminator: str = ""
    ) -> str:
        """Compose a deterministic edge id from its endpoints and relationship."""
        key = f"{source_id}\x1f{relationship.value}\x1f{target_id}\x1f{discriminator}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        source_id: str,
        relationship: RelationshipType,
        target_id: str,
        *,
        created_at: str = "",
        metadata: dict[str, str] | None = None,
        discriminator: str = "",
    ) -> GraphEdge:
        """Build an edge with a deterministic id."""
        return cls(
            edge_id=cls.make_id(source_id, relationship, target_id, discriminator),
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
            created_at=created_at,
            metadata=dict(metadata) if metadata else {},
        )

    def to_dict(self) -> dict[str, object]:
        """Serialise the edge into JSON-compatible primitives."""
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship.value,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GraphPath:
    """An ordered path of nodes connected by edges."""

    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()

    @property
    def length(self) -> int:
        """The number of edges (hops) in the path."""
        return len(self.edges)

    def to_dict(self) -> dict[str, object]:
        """Serialise the path into JSON-compatible primitives."""
        return {
            "length": self.length,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


@dataclass(frozen=True)
class GraphQuery:
    """A deterministic traversal request over the graph."""

    node_id: str | None = None
    node_types: frozenset[EntityType] = frozenset()
    relationships: frozenset[RelationshipType] = frozenset()
    direction: str = "both"
    depth: int = 1
    limit: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the query into JSON-compatible primitives."""
        return {
            "node_id": self.node_id,
            "node_types": sorted(member.value for member in self.node_types),
            "relationships": sorted(member.value for member in self.relationships),
            "direction": self.direction,
            "depth": self.depth,
            "limit": self.limit,
        }


@dataclass(frozen=True)
class GraphResult:
    """A set of nodes and edges (and optional paths) returned by a query."""

    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()
    paths: tuple[GraphPath, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialise the result into JSON-compatible primitives."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "paths": [path.to_dict() for path in self.paths],
        }
