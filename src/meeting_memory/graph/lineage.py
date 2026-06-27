"""Lineage queries over the organizational memory graph.

A lineage is the ordered chain a memory forms with its predecessors and
successors along a single relationship. Decisions evolve through ``SUPERSEDES``
edges (a newer decision supersedes an older one); repeated risks/decisions across
meetings form ``CONNECTED_TO`` chains. Both follow the same convention — an edge
points from the *newer* node to the *older* one — so a single deterministic
routine orders any such chain oldest-to-newest.
"""

from __future__ import annotations

from itertools import pairwise

from .models import GraphEdge, GraphPath, RelationshipType
from .store import GraphStore


def relationship_lineage(
    store: GraphStore, node_id: str, relationship: RelationshipType, *, max_depth: int = 256
) -> GraphPath:
    """Return the lineage chain through ``relationship``, ordered oldest-to-newest."""
    if not store.has_node(node_id):
        return GraphPath()

    relationships = frozenset({relationship})
    members = _component(store, node_id, relationships, max_depth)

    # ``newer -> older`` edges restricted to the component.
    older_of: dict[str, list[str]] = {}
    newer_of: dict[str, list[str]] = {}
    edge_by_pair: dict[tuple[str, str], GraphEdge] = {}
    for member in members:
        for edge in store.outgoing(member, relationships):
            # Every rel-connected target is in ``members`` (component is built over
            # the same relationship in both directions), so no membership guard.
            older_of.setdefault(member, []).append(edge.target_id)
            newer_of.setdefault(edge.target_id, []).append(member)
            edge_by_pair[(member, edge.target_id)] = edge

    newest = sorted(member for member in members if member not in newer_of)
    start = newest[0] if newest else sorted(members)[0]

    ordered: list[str] = []
    seen: set[str] = set()
    current: str | None = start
    while current is not None and current not in seen:
        ordered.append(current)
        seen.add(current)
        candidates = sorted(target for target in older_of.get(current, []) if target not in seen)
        current = candidates[0] if candidates else None

    ordered.reverse()  # oldest first
    nodes = tuple(store.get_node(node_id) for node_id in ordered)
    edges = tuple(edge_by_pair[(newer, older)] for older, newer in pairwise(ordered))
    return GraphPath(nodes=nodes, edges=edges)


def decision_lineage(store: GraphStore, node_id: str) -> GraphPath:
    """Return how a decision evolved via ``SUPERSEDES`` edges."""
    return relationship_lineage(store, node_id, RelationshipType.SUPERSEDES)


def risk_lineage(store: GraphStore, node_id: str) -> GraphPath:
    """Return how a repeated risk/decision evolved via ``CONNECTED_TO`` edges."""
    return relationship_lineage(store, node_id, RelationshipType.CONNECTED_TO)


def _component(
    store: GraphStore,
    node_id: str,
    relationships: frozenset[RelationshipType],
    max_depth: int,
) -> set[str]:
    """Return all nodes reachable from ``node_id`` over ``relationships`` (undirected)."""
    members: set[str] = {node_id}
    frontier = [node_id]
    for _ in range(max_depth):
        discovered: list[str] = []
        for current in frontier:
            neighbors = [edge.target_id for edge in store.outgoing(current, relationships)]
            neighbors += [edge.source_id for edge in store.incoming(current, relationships)]
            for neighbor in neighbors:
                if neighbor not in members:
                    members.add(neighbor)
                    discovered.append(neighbor)
        if not discovered:
            break
        frontier = sorted(discovered)
    return members


__all__ = ["decision_lineage", "relationship_lineage", "risk_lineage"]
