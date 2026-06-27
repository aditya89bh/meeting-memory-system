"""Graph service: build and query the organizational memory graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..graph import (
    EntityType,
    GraphEdge,
    GraphEngine,
    GraphNode,
    GraphPath,
    GraphResult,
    RelationshipType,
    SQLiteGraphStore,
    build_graph,
    export_graph,
)
from ..storage import SQLiteMemoryStore


@dataclass(frozen=True)
class GraphSummary:
    """A summary of the graph plus an optionally filtered node listing."""

    nodes: int
    edges: int
    by_node_type: dict[str, int] = field(default_factory=dict)
    by_relationship: dict[str, int] = field(default_factory=dict)
    listed: tuple[GraphNode, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialise the summary into JSON-compatible primitives."""
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "by_node_type": dict(sorted(self.by_node_type.items())),
            "by_relationship": dict(sorted(self.by_relationship.items())),
            "listed": [node.to_dict() for node in self.listed],
        }


@dataclass(frozen=True)
class NeighborhoodResult:
    """The start node together with its traversal result."""

    node: GraphNode
    result: GraphResult

    def to_dict(self) -> dict[str, object]:
        """Serialise the neighbourhood into JSON-compatible primitives."""
        payload = self.result.to_dict()
        payload["node"] = self.node.to_dict()
        return payload


class GraphService:
    """Build the knowledge graph and answer traversal queries."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    def _open(self) -> SQLiteGraphStore:
        """Rebuild the graph from stored memory and return an open graph store."""
        graph_store = SQLiteGraphStore(self.db)
        with SQLiteMemoryStore(self.db) as memory_store:
            build_graph(memory_store, graph_store)
        return graph_store

    def summary(
        self,
        *,
        node_types: frozenset[EntityType] | None = None,
        limit: int | None = None,
    ) -> GraphSummary:
        """Return graph counts plus an optionally filtered node listing."""
        store = self._open()
        try:
            by_node_type: dict[str, int] = {}
            for node in store.list_nodes():
                key = node.node_type.value
                by_node_type[key] = by_node_type.get(key, 0) + 1
            by_relationship: dict[str, int] = {}
            for edge in store.list_edges():
                key = edge.relationship.value
                by_relationship[key] = by_relationship.get(key, 0) + 1
            listed = tuple(store.list_nodes(node_types=node_types, limit=limit))
            return GraphSummary(
                nodes=store.count_nodes(),
                edges=store.count_edges(),
                by_node_type=by_node_type,
                by_relationship=by_relationship,
                listed=listed,
            )
        finally:
            store.close()

    def neighbors(
        self,
        node_id: str,
        *,
        depth: int = 1,
        relationships: frozenset[RelationshipType] | None = None,
        node_types: frozenset[EntityType] | None = None,
        limit: int | None = None,
    ) -> NeighborhoodResult:
        """Traverse the graph from a node and return it with its neighbourhood."""
        store = self._open()
        try:
            node = store.get_node(node_id)
            result = GraphEngine(store).neighbors(
                node_id,
                depth=depth,
                relationships=relationships,
                node_types=node_types,
                limit=limit,
            )
            return NeighborhoodResult(node=node, result=result)
        finally:
            store.close()

    def path(
        self,
        source: str,
        target: str,
        *,
        max_depth: int = 6,
        relationships: frozenset[RelationshipType] | None = None,
    ) -> GraphPath | None:
        """Return a deterministic shortest path between two nodes, if any."""
        store = self._open()
        try:
            return GraphEngine(store).find_path(
                source, target, max_depth=max_depth, relationships=relationships
            )
        finally:
            store.close()

    def export(
        self,
        fmt: str,
        *,
        node_types: frozenset[EntityType] | None = None,
        limit: int | None = None,
    ) -> str | dict[str, object]:
        """Export the graph (optionally filtered) as JSON, Mermaid, or DOT."""
        store = self._open()
        try:
            nodes = store.list_nodes(node_types=node_types, limit=limit)
            keep = {node.node_id for node in nodes}
            edges: list[GraphEdge] = [
                edge
                for edge in store.list_edges()
                if edge.source_id in keep and edge.target_id in keep
            ]
            return export_graph(nodes, edges, fmt)
        finally:
            store.close()
