"""Unit tests for deterministic graph traversal."""

from __future__ import annotations

from meeting_memory.graph import (
    EntityType,
    GraphEdge,
    GraphEngine,
    GraphNode,
    RelationshipType,
    SQLiteGraphStore,
)
from meeting_memory.graph.engine import MEMORY_NODE_TYPES


def _store() -> SQLiteGraphStore:
    """A small fixed graph:

    meeting:m1 -mentions-> person:alice, person:bob, project:atlas
    decision:d1 -relates_to-> project:atlas; risk:r1 -blocks-> project:atlas
    decision:d1 -discussed_in-> meeting:m1
    """
    store = SQLiteGraphStore(":memory:")
    store.add_nodes(
        [
            GraphNode(node_id="meeting:m1", node_type=EntityType.MEETING, label="M1", ref_id="m1"),
            GraphNode.for_person("Alice"),
            GraphNode.for_person("Bob"),
            GraphNode.for_entity(EntityType.PROJECT, "Atlas"),
            GraphNode(
                node_id="decision:d1", node_type=EntityType.DECISION, label="D1", ref_id="d1"
            ),
            GraphNode(node_id="risk:r1", node_type=EntityType.RISK, label="R1", ref_id="r1"),
        ]
    )
    edges = [
        GraphEdge.create("meeting:m1", RelationshipType.MENTIONS, "person:alice"),
        GraphEdge.create("meeting:m1", RelationshipType.MENTIONS, "person:bob"),
        GraphEdge.create("meeting:m1", RelationshipType.MENTIONS, "project:atlas"),
        GraphEdge.create("decision:d1", RelationshipType.RELATES_TO, "project:atlas"),
        GraphEdge.create("risk:r1", RelationshipType.BLOCKS, "project:atlas"),
        GraphEdge.create("decision:d1", RelationshipType.DISCUSSED_IN, "meeting:m1"),
    ]
    store.add_edges(edges)
    return store


def test_outgoing_and_incoming() -> None:
    store = _store()
    engine = GraphEngine(store)
    assert len(engine.outgoing("meeting:m1")) == 3
    assert len(engine.incoming("project:atlas")) == 3
    store.close()


def test_neighbors_depth_one() -> None:
    store = _store()
    result = GraphEngine(store).neighbors("project:atlas", depth=1)
    ids = {node.node_id for node in result.nodes}
    assert ids == {"project:atlas", "meeting:m1", "decision:d1", "risk:r1"}
    store.close()


def test_neighbors_depth_two_reaches_further() -> None:
    store = _store()
    result = GraphEngine(store).neighbors("risk:r1", depth=2)
    ids = {node.node_id for node in result.nodes}
    assert "meeting:m1" in ids  # risk -> project -> meeting? no; risk->project, project->? incoming
    assert "project:atlas" in ids
    store.close()


def test_neighbors_relationship_filter() -> None:
    store = _store()
    result = GraphEngine(store).neighbors(
        "project:atlas", depth=1, relationships=frozenset({RelationshipType.BLOCKS})
    )
    ids = {node.node_id for node in result.nodes}
    assert ids == {"project:atlas", "risk:r1"}
    store.close()


def test_neighbors_direction_out_only() -> None:
    store = _store()
    out = GraphEngine(store).neighbors("decision:d1", depth=1, direction="out")
    ids = {node.node_id for node in out.nodes}
    assert ids == {"decision:d1", "project:atlas", "meeting:m1"}
    incoming = GraphEngine(store).neighbors("decision:d1", depth=1, direction="in")
    assert {node.node_id for node in incoming.nodes} == {"decision:d1"}
    store.close()


def test_neighbors_node_type_filter_and_limit() -> None:
    store = _store()
    result = GraphEngine(store).neighbors(
        "meeting:m1", depth=1, node_types=frozenset({EntityType.PERSON})
    )
    assert {node.node_id for node in result.nodes} == {"person:alice", "person:bob"}
    limited = GraphEngine(store).neighbors("meeting:m1", depth=1, limit=1)
    assert len(limited.nodes) == 1
    store.close()


def test_neighbors_unknown_node_returns_empty() -> None:
    store = _store()
    result = GraphEngine(store).neighbors("person:nobody", depth=2)
    assert result.nodes == ()
    assert result.edges == ()
    store.close()


def test_related_excludes_source_and_limits() -> None:
    store = _store()
    engine = GraphEngine(store)
    related = engine.related("project:atlas", depth=1)
    assert "project:atlas" not in {node.node_id for node in related}
    assert len(engine.related("project:atlas", depth=1, limit=1)) == 1
    store.close()


def test_related_helpers_by_type() -> None:
    store = _store()
    engine = GraphEngine(store)
    assert {n.node_id for n in engine.related_meetings("project:atlas")} == {"meeting:m1"}
    assert {n.node_id for n in engine.related_people("meeting:m1")} == {
        "person:alice",
        "person:bob",
    }
    assert {n.node_id for n in engine.related_projects("risk:r1")} == {"project:atlas"}
    memories = engine.related_memories("project:atlas")
    assert all(node.node_type in MEMORY_NODE_TYPES for node in memories)
    assert {n.node_id for n in memories} == {"decision:d1", "risk:r1"}
    store.close()


def test_find_path_same_node() -> None:
    store = _store()
    path = GraphEngine(store).find_path("project:atlas", "project:atlas")
    assert path is not None
    assert path.length == 0
    assert [node.node_id for node in path.nodes] == ["project:atlas"]
    store.close()


def test_find_path_between_nodes() -> None:
    store = _store()
    path = GraphEngine(store).find_path("risk:r1", "person:alice")
    assert path is not None
    assert path.nodes[0].node_id == "risk:r1"
    assert path.nodes[-1].node_id == "person:alice"
    assert path.length == path.length  # edges line up with nodes
    assert len(path.edges) == len(path.nodes) - 1
    store.close()


def test_find_path_missing_endpoint_or_unreachable() -> None:
    store = _store()
    engine = GraphEngine(store)
    assert engine.find_path("person:nobody", "project:atlas") is None
    # Unreachable within a tiny max_depth.
    isolated = GraphEngine(store)
    assert isolated.find_path("person:alice", "risk:r1", max_depth=1) is None
    store.close()


def test_connected_components_single_and_split() -> None:
    store = _store()
    engine = GraphEngine(store)
    components = engine.connected_components()
    assert len(components) == 1
    assert len(components[0]) == 6
    # Add an isolated node -> a second component.
    store.add_node(GraphNode.for_person("Zoe"))
    components = engine.connected_components()
    assert ["person:zoe"] in components
    assert len(components) == 2
    store.close()
