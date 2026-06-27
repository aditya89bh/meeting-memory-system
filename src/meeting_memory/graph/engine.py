"""Deterministic traversal over the organizational memory graph.

``GraphEngine`` reads a :class:`GraphStore` and answers the standard graph
questions — neighbours, incoming/outgoing edges, reachability, shortest path,
and connected components — plus convenience helpers for finding related
memories, meetings, people, and projects. Every traversal explores neighbours in
a fixed (sorted) order, so results and tie-breaks are fully reproducible.
"""

from __future__ import annotations

from collections import deque

from .lineage import decision_lineage, relationship_lineage, risk_lineage
from .models import (
    EntityType,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphResult,
    RelationshipType,
)
from .store import GraphStore

# Node types that represent extracted memories (used by ``related_memories``).
MEMORY_NODE_TYPES: frozenset[EntityType] = frozenset(
    {
        EntityType.MEMORY,
        EntityType.DECISION,
        EntityType.COMMITMENT,
        EntityType.RISK,
        EntityType.QUESTION,
        EntityType.ASSUMPTION,
        EntityType.FACT,
    }
)


class GraphEngine:
    """Read-only, deterministic traversal over a graph store."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    # -- edge accessors --------------------------------------------------------

    def outgoing(
        self, node_id: str, relationships: frozenset[RelationshipType] | None = None
    ) -> list[GraphEdge]:
        """Return edges leaving ``node_id`` in deterministic order."""
        return self._store.outgoing(node_id, relationships)

    def incoming(
        self, node_id: str, relationships: frozenset[RelationshipType] | None = None
    ) -> list[GraphEdge]:
        """Return edges entering ``node_id`` in deterministic order."""
        return self._store.incoming(node_id, relationships)

    # -- neighbourhoods --------------------------------------------------------

    def neighbors(
        self,
        node_id: str,
        *,
        depth: int = 1,
        relationships: frozenset[RelationshipType] | None = None,
        direction: str = "both",
        node_types: frozenset[EntityType] | None = None,
        limit: int | None = None,
    ) -> GraphResult:
        """Return the nodes and edges within ``depth`` hops of ``node_id``."""
        visited: set[str] = {node_id}
        frontier: list[str] = [node_id]
        used_edges: dict[str, GraphEdge] = {}

        for _ in range(max(depth, 0)):
            discovered: list[str] = []
            for current in frontier:
                for neighbor, edge in self._adjacency(current, direction, relationships):
                    used_edges.setdefault(edge.edge_id, edge)
                    if neighbor not in visited:
                        visited.add(neighbor)
                        discovered.append(neighbor)
            if not discovered:
                break
            frontier = sorted(discovered)

        nodes = self._nodes_for(sorted(visited))
        if node_types is not None:
            nodes = [node for node in nodes if node.node_type in node_types]
        if limit is not None:
            nodes = nodes[:limit]
        edges = [used_edges[edge_id] for edge_id in sorted(used_edges)]
        return GraphResult(nodes=tuple(nodes), edges=tuple(edges))

    def related(
        self,
        node_id: str,
        *,
        depth: int = 1,
        relationships: frozenset[RelationshipType] | None = None,
        direction: str = "both",
        node_types: frozenset[EntityType] | None = None,
        limit: int | None = None,
    ) -> list[GraphNode]:
        """Return nodes reachable from ``node_id`` (excluding it), in order."""
        result = self.neighbors(
            node_id,
            depth=depth,
            relationships=relationships,
            direction=direction,
            node_types=node_types,
            limit=None,
        )
        related = [node for node in result.nodes if node.node_id != node_id]
        if limit is not None:
            related = related[:limit]
        return related

    def related_memories(self, node_id: str, *, depth: int = 2) -> list[GraphNode]:
        """Return memory nodes related to ``node_id``."""
        return self.related(node_id, depth=depth, node_types=MEMORY_NODE_TYPES)

    def related_meetings(self, node_id: str, *, depth: int = 2) -> list[GraphNode]:
        """Return meeting nodes related to ``node_id``."""
        return self.related(node_id, depth=depth, node_types=frozenset({EntityType.MEETING}))

    def related_people(self, node_id: str, *, depth: int = 2) -> list[GraphNode]:
        """Return person nodes related to ``node_id``."""
        return self.related(node_id, depth=depth, node_types=frozenset({EntityType.PERSON}))

    def related_projects(self, node_id: str, *, depth: int = 2) -> list[GraphNode]:
        """Return project nodes related to ``node_id``."""
        return self.related(node_id, depth=depth, node_types=frozenset({EntityType.PROJECT}))

    # -- paths and components --------------------------------------------------

    def find_path(
        self,
        source_id: str,
        target_id: str,
        *,
        max_depth: int = 6,
        relationships: frozenset[RelationshipType] | None = None,
    ) -> GraphPath | None:
        """Return the shortest path between two nodes, or ``None`` if unreachable."""
        if not self._store.has_node(source_id) or not self._store.has_node(target_id):
            return None
        if source_id == target_id:
            return GraphPath(nodes=(self._store.get_node(source_id),), edges=())

        came_from: dict[str, tuple[str, GraphEdge]] = {}
        visited: set[str] = {source_id}
        queue: deque[tuple[str, int]] = deque([(source_id, 0)])
        while queue:
            current, hops = queue.popleft()
            if hops >= max_depth:
                continue
            for neighbor, edge in sorted(
                self._adjacency(current, "both", relationships),
                key=lambda item: (item[0], item[1].edge_id),
            ):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                came_from[neighbor] = (current, edge)
                if neighbor == target_id:
                    return self._reconstruct(source_id, target_id, came_from)
                queue.append((neighbor, hops + 1))
        return None

    def connected_components(
        self, relationships: frozenset[RelationshipType] | None = None
    ) -> list[list[str]]:
        """Return connected components (undirected), each a sorted id list."""
        adjacency: dict[str, set[str]] = {}
        for edge in self._store.list_edges(relationships=relationships):
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)
            adjacency.setdefault(edge.target_id, set()).add(edge.source_id)

        all_ids = [node.node_id for node in self._store.list_nodes()]
        visited: set[str] = set()
        components: list[list[str]] = []
        for start in all_ids:
            if start in visited:
                continue
            component: list[str] = []
            queue: deque[str] = deque([start])
            visited.add(start)
            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor in sorted(adjacency.get(current, set())):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(sorted(component))
        components.sort(key=lambda ids: ids[0])
        return components

    # -- lineage ---------------------------------------------------------------

    def lineage(self, node_id: str, relationship: RelationshipType) -> GraphPath:
        """Return the lineage chain through ``relationship``, oldest-to-newest."""
        return relationship_lineage(self._store, node_id, relationship)

    def decision_lineage(self, node_id: str) -> GraphPath:
        """Return how a decision evolved via ``SUPERSEDES`` edges."""
        return decision_lineage(self._store, node_id)

    def risk_lineage(self, node_id: str) -> GraphPath:
        """Return how a repeated risk/decision evolved via ``CONNECTED_TO`` edges."""
        return risk_lineage(self._store, node_id)

    # -- internal helpers ------------------------------------------------------

    def _adjacency(
        self,
        node_id: str,
        direction: str,
        relationships: frozenset[RelationshipType] | None,
    ) -> list[tuple[str, GraphEdge]]:
        result: list[tuple[str, GraphEdge]] = []
        if direction in ("out", "both"):
            for edge in self._store.outgoing(node_id, relationships):
                result.append((edge.target_id, edge))
        if direction in ("in", "both"):
            for edge in self._store.incoming(node_id, relationships):
                result.append((edge.source_id, edge))
        return result

    def _nodes_for(self, node_ids: list[str]) -> list[GraphNode]:
        nodes: list[GraphNode] = []
        for node_id in node_ids:
            if self._store.has_node(node_id):
                nodes.append(self._store.get_node(node_id))
        return nodes

    def _reconstruct(
        self, source_id: str, target_id: str, came_from: dict[str, tuple[str, GraphEdge]]
    ) -> GraphPath:
        node_ids: list[str] = [target_id]
        edges: list[GraphEdge] = []
        current = target_id
        while current != source_id:
            previous, edge = came_from[current]
            edges.append(edge)
            node_ids.append(previous)
            current = previous
        node_ids.reverse()
        edges.reverse()
        nodes = tuple(self._store.get_node(node_id) for node_id in node_ids)
        return GraphPath(nodes=nodes, edges=tuple(edges))


__all__ = ["MEMORY_NODE_TYPES", "GraphEngine"]
