"""Build and persist the organizational memory graph from stored memories.

``build_graph`` reads every meeting and memory from a :class:`MemoryStore`,
creates the core nodes (meetings, memories, people) and extracted entity nodes,
derives the edges, and writes them to a :class:`GraphStore`. It is deterministic
and idempotent: node and edge ids are content-derived, so running it repeatedly
on the same data adds nothing new and never overwrites existing relationships.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..storage import MemoryStore, StoredMeeting, StoredMemory
from .entities import DEFAULT_VOCABULARY, EntityVocabulary, extract_entities
from .models import GraphEdge, GraphNode, RelationshipType
from .relationships import meeting_relationships
from .store import GraphStore


@dataclass(frozen=True)
class GraphBuildResult:
    """Summary of a graph build."""

    nodes_added: int
    edges_added: int
    node_total: int
    edge_total: int

    def summary_lines(self) -> list[str]:
        """Human-readable summary lines for CLI output."""
        return [
            f"Graph built: {self.node_total} nodes, {self.edge_total} edges",
            f"{self.nodes_added} nodes added, {self.edges_added} edges added",
        ]

    def to_dict(self) -> dict[str, object]:
        """Serialise the build summary into JSON-compatible primitives."""
        return {
            "nodes_added": self.nodes_added,
            "edges_added": self.edges_added,
            "node_total": self.node_total,
            "edge_total": self.edge_total,
        }


def build_graph(
    memory_store: MemoryStore,
    graph_store: GraphStore,
    *,
    vocabulary: EntityVocabulary = DEFAULT_VOCABULARY,
) -> GraphBuildResult:
    """Build the graph from ``memory_store`` and persist it into ``graph_store``."""
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}
    memory_node_index: dict[str, str] = {}
    all_memories: list[StoredMemory] = []

    for meeting in memory_store.list_meetings():
        memories = memory_store.find_by_meeting(meeting.meeting_id)
        all_memories.extend(memories)
        _register_core_nodes(meeting, memories, nodes, memory_node_index)

        extraction = extract_entities(meeting, memories, vocabulary)
        for node in extraction.nodes.values():
            nodes.setdefault(node.node_id, node)

        for edge in meeting_relationships(meeting, memories, extraction):
            edges.setdefault(edge.edge_id, edge)

    for edge in _supersedes_edges(all_memories, memory_node_index):
        edges.setdefault(edge.edge_id, edge)

    nodes_added = graph_store.add_nodes(nodes[node_id] for node_id in sorted(nodes))
    edges_added = graph_store.add_edges(edges[edge_id] for edge_id in sorted(edges))
    return GraphBuildResult(
        nodes_added=nodes_added,
        edges_added=edges_added,
        node_total=graph_store.count_nodes(),
        edge_total=graph_store.count_edges(),
    )


def _register_core_nodes(
    meeting: StoredMeeting,
    memories: list[StoredMemory],
    nodes: dict[str, GraphNode],
    memory_node_index: dict[str, str],
) -> None:
    """Create meeting, person, and memory nodes for one meeting."""
    meeting_node = GraphNode.for_meeting(meeting)
    nodes.setdefault(meeting_node.node_id, meeting_node)

    for participant in meeting.participants:
        person = GraphNode.for_person(participant, created_at=meeting.created_at)
        nodes.setdefault(person.node_id, person)

    for memory in memories:
        memory_node = GraphNode.for_memory(memory)
        nodes.setdefault(memory_node.node_id, memory_node)
        memory_node_index[memory.memory_id] = memory_node.node_id
        for name in (memory.speaker, memory.metadata.get("owner")):
            if name:
                person = GraphNode.for_person(name, created_at=meeting.created_at)
                nodes.setdefault(person.node_id, person)


def _supersedes_edges(
    memories: list[StoredMemory], memory_node_index: dict[str, str]
) -> list[GraphEdge]:
    """Create SUPERSEDES edges from each memory's ``superseded_by`` pointer."""
    edges: list[GraphEdge] = []
    for memory in memories:
        target = memory.superseded_by
        if target and target in memory_node_index and memory.memory_id in memory_node_index:
            edges.append(
                GraphEdge.create(
                    memory_node_index[target],
                    RelationshipType.SUPERSEDES,
                    memory_node_index[memory.memory_id],
                    created_at=memory.updated_at,
                )
            )
    return edges


__all__ = ["GraphBuildResult", "build_graph"]
