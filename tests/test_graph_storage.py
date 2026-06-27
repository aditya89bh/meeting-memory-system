"""Unit tests for graph storage: persistence, idempotency, and migration safety."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from meeting_memory.exceptions import NodeNotFoundError
from meeting_memory.graph import (
    EntityType,
    GraphEdge,
    GraphNode,
    RelationshipType,
    SQLiteGraphStore,
)
from meeting_memory.storage import SQLiteMemoryStore, import_meeting
from meeting_memory.storage.migrations import SCHEMA_VERSION, apply_migrations


def _nodes() -> tuple[GraphNode, GraphNode]:
    return (
        GraphNode.for_person("Alice"),
        GraphNode.for_entity(EntityType.PROJECT, "Atlas"),
    )


def test_add_nodes_is_idempotent() -> None:
    store = SQLiteGraphStore(":memory:")
    alice, atlas = _nodes()
    assert store.add_nodes([alice, atlas, alice]) == 2
    assert store.add_node(alice) is False
    assert store.count_nodes() == 2
    store.close()


def test_get_node_and_metadata_roundtrip() -> None:
    store = SQLiteGraphStore(":memory:")
    node = GraphNode(
        node_id="meeting:m1",
        node_type=EntityType.MEETING,
        label="Kickoff",
        ref_id="m1",
        metadata={"date": "2026-01-05"},
    )
    store.add_node(node)
    loaded = store.get_node("meeting:m1")
    assert loaded.label == "Kickoff"
    assert loaded.metadata == {"date": "2026-01-05"}
    store.close()


def test_get_missing_node_raises() -> None:
    store = SQLiteGraphStore(":memory:")
    with pytest.raises(NodeNotFoundError):
        store.get_node("person:nobody")
    assert store.has_node("person:nobody") is False
    store.close()


def test_list_nodes_filters_by_type_and_limit() -> None:
    store = SQLiteGraphStore(":memory:")
    alice, atlas = _nodes()
    store.add_nodes([alice, atlas])
    people = store.list_nodes(node_types=frozenset({EntityType.PERSON}))
    assert [node.node_id for node in people] == ["person:alice"]
    assert len(store.list_nodes(limit=1)) == 1
    assert store.list_nodes(limit=1, offset=1)[0].node_id == "project:atlas"
    # Offset without a limit exercises the LIMIT -1 OFFSET path.
    assert store.list_nodes(offset=1)[0].node_id == "project:atlas"
    store.close()


def test_add_edges_idempotent_with_metadata() -> None:
    store = SQLiteGraphStore(":memory:")
    alice, atlas = _nodes()
    store.add_nodes([alice, atlas])
    edge = GraphEdge.create(
        alice.node_id, RelationshipType.MENTIONS, atlas.node_id, metadata={"meeting_id": "m1"}
    )
    assert store.add_edge(edge) is True
    assert store.add_edge(edge) is False
    assert store.add_edges([edge]) == 0
    assert store.count_edges() == 1
    stored = store.list_edges()[0]
    assert stored.metadata == {"meeting_id": "m1"}
    store.close()


def test_outgoing_incoming_and_relationship_filter() -> None:
    store = SQLiteGraphStore(":memory:")
    alice, atlas = _nodes()
    store.add_nodes([alice, atlas])
    store.add_edge(GraphEdge.create(alice.node_id, RelationshipType.MENTIONS, atlas.node_id))
    store.add_edge(GraphEdge.create(alice.node_id, RelationshipType.OWNED_BY, atlas.node_id))
    assert len(store.outgoing(alice.node_id)) == 2
    assert len(store.incoming(atlas.node_id)) == 2
    only_mentions = store.outgoing(
        alice.node_id, relationships=frozenset({RelationshipType.MENTIONS})
    )
    assert [edge.relationship for edge in only_mentions] == [RelationshipType.MENTIONS]
    filtered = store.list_edges(
        target_id=atlas.node_id, relationships=frozenset({RelationshipType.OWNED_BY})
    )
    assert len(filtered) == 1
    store.close()


def test_context_manager_closes() -> None:
    with SQLiteGraphStore(":memory:") as store:
        store.add_node(GraphNode.for_person("Alice"))
        assert store.count_nodes() == 1


def test_graph_store_creates_parent_dir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "graph.db"
    store = SQLiteGraphStore(target)
    store.add_node(GraphNode.for_person("Alice"))
    store.close()
    assert target.exists()


def test_migration_is_additive_for_existing_v1_database(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    # Simulate an old database stuck at schema version 1 (no graph tables).
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA user_version = 1")
    connection.execute("CREATE TABLE meetings (meeting_id TEXT PRIMARY KEY)")
    connection.execute("INSERT INTO meetings (meeting_id) VALUES ('legacy')")
    connection.commit()
    connection.close()

    # Opening with the current code upgrades in place without losing data.
    upgraded = sqlite3.connect(db)
    assert apply_migrations(upgraded) == SCHEMA_VERSION
    rows = upgraded.execute("SELECT meeting_id FROM meetings").fetchall()
    assert rows == [("legacy",)]
    tables = {
        row[0]
        for row in upgraded.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"graph_nodes", "graph_edges"} <= tables
    upgraded.close()


def test_graph_shares_database_with_memory_store(tmp_path: Path) -> None:
    db = tmp_path / "shared.db"
    transcript = tmp_path / "m.txt"
    transcript.write_text(
        "---\ntitle: T\ndate: 2026-01-05\n---\n[00:00:05] Alice: We decided to use Postgres.\n",
        encoding="utf-8",
    )
    with SQLiteMemoryStore(db) as memory_store:
        import_meeting(transcript, memory_store)
    graph_store = SQLiteGraphStore(db)
    graph_store.add_node(GraphNode.for_person("Alice"))
    assert graph_store.has_node("person:alice")
    graph_store.close()
