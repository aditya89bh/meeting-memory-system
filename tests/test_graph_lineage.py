"""Unit tests for decision and risk lineage."""

from __future__ import annotations

from meeting_memory.graph import (
    EntityType,
    GraphEdge,
    GraphEngine,
    GraphNode,
    RelationshipType,
    SQLiteGraphStore,
    decision_lineage,
    relationship_lineage,
    risk_lineage,
)


def _decision(node_id: str, label: str) -> GraphNode:
    return GraphNode(node_id=node_id, node_type=EntityType.DECISION, label=label, ref_id=node_id)


def _chain_store() -> SQLiteGraphStore:
    """A -> B -> C supersede chain (edges point newer -> older)."""
    store = SQLiteGraphStore(":memory:")
    store.add_nodes(
        [_decision("decision:a", "A"), _decision("decision:b", "B"), _decision("decision:c", "C")]
    )
    store.add_edge(GraphEdge.create("decision:b", RelationshipType.SUPERSEDES, "decision:a"))
    store.add_edge(GraphEdge.create("decision:c", RelationshipType.SUPERSEDES, "decision:b"))
    return store


def test_decision_lineage_orders_oldest_to_newest_from_middle() -> None:
    store = _chain_store()
    path = decision_lineage(store, "decision:b")
    assert [node.node_id for node in path.nodes] == ["decision:a", "decision:b", "decision:c"]
    assert path.length == 2
    store.close()


def test_decision_lineage_from_oldest_and_newest() -> None:
    store = _chain_store()
    assert [n.node_id for n in decision_lineage(store, "decision:a").nodes] == [
        "decision:a",
        "decision:b",
        "decision:c",
    ]
    assert [n.node_id for n in decision_lineage(store, "decision:c").nodes] == [
        "decision:a",
        "decision:b",
        "decision:c",
    ]
    store.close()


def test_lineage_single_node_has_no_edges() -> None:
    store = SQLiteGraphStore(":memory:")
    store.add_node(_decision("decision:solo", "Solo"))
    path = decision_lineage(store, "decision:solo")
    assert [node.node_id for node in path.nodes] == ["decision:solo"]
    assert path.edges == ()
    store.close()


def test_lineage_missing_node_is_empty() -> None:
    store = SQLiteGraphStore(":memory:")
    path = decision_lineage(store, "decision:ghost")
    assert path.nodes == ()
    assert path.edges == ()
    store.close()


def test_engine_lineage_delegates() -> None:
    store = _chain_store()
    engine = GraphEngine(store)
    assert [n.node_id for n in engine.decision_lineage("decision:a").nodes] == [
        "decision:a",
        "decision:b",
        "decision:c",
    ]
    generic = engine.lineage("decision:a", RelationshipType.SUPERSEDES)
    assert generic.length == 2
    store.close()


def test_engine_risk_lineage_delegates() -> None:
    store = SQLiteGraphStore(":memory:")
    store.add_nodes(
        [
            GraphNode(node_id="risk:r1", node_type=EntityType.RISK, label="R1", ref_id="r1"),
            GraphNode(node_id="risk:r2", node_type=EntityType.RISK, label="R2", ref_id="r2"),
        ]
    )
    store.add_edge(GraphEdge.create("risk:r2", RelationshipType.CONNECTED_TO, "risk:r1"))
    path = GraphEngine(store).risk_lineage("risk:r1")
    assert [node.node_id for node in path.nodes] == ["risk:r1", "risk:r2"]
    store.close()


def test_risk_lineage_follows_connected_to() -> None:
    store = SQLiteGraphStore(":memory:")
    store.add_nodes(
        [
            GraphNode(node_id="risk:r1", node_type=EntityType.RISK, label="R1", ref_id="r1"),
            GraphNode(node_id="risk:r2", node_type=EntityType.RISK, label="R2", ref_id="r2"),
        ]
    )
    store.add_edge(
        GraphEdge.create(
            "risk:r2", RelationshipType.CONNECTED_TO, "risk:r1", discriminator="repeated_content"
        )
    )
    path = risk_lineage(store, "risk:r1")
    assert [node.node_id for node in path.nodes] == ["risk:r1", "risk:r2"]
    store.close()


def test_relationship_lineage_respects_max_depth() -> None:
    store = _chain_store()
    # A max_depth smaller than the chain stops traversal early but stays valid.
    path = relationship_lineage(store, "decision:a", RelationshipType.SUPERSEDES, max_depth=1)
    assert path.nodes[0].node_id == "decision:a"
    store.close()


def test_relationship_lineage_branch_is_deterministic() -> None:
    # A newest node with two older targets; ordering must be reproducible.
    store = SQLiteGraphStore(":memory:")
    store.add_nodes(
        [_decision("decision:a", "A"), _decision("decision:b", "B"), _decision("decision:c", "C")]
    )
    store.add_edge(GraphEdge.create("decision:c", RelationshipType.SUPERSEDES, "decision:a"))
    store.add_edge(GraphEdge.create("decision:c", RelationshipType.SUPERSEDES, "decision:b"))
    first = relationship_lineage(store, "decision:a", RelationshipType.SUPERSEDES)
    second = relationship_lineage(store, "decision:b", RelationshipType.SUPERSEDES)
    assert [n.node_id for n in first.nodes] == [n.node_id for n in second.nodes]
    assert first.nodes[-1].node_id == "decision:c"
    store.close()
