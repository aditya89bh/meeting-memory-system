"""Unit tests for graph models: nodes, edges, paths, queries, and ids."""

from __future__ import annotations

from meeting_memory.graph import (
    RELATIONSHIP_REGISTRY,
    EntityType,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphRelationship,
    GraphResult,
    RelationshipType,
    slugify,
)
from meeting_memory.storage import MemoryStatus, StoredMeeting, StoredMemory


def _meeting() -> StoredMeeting:
    return StoredMeeting(
        meeting_id="m1",
        transcript_hash="h",
        created_at="2026-01-01T00:00:00+00:00",
        title="Project Atlas Kickoff",
        date="2026-01-05",
        participants=("Alice", "Bob"),
    )


def _memory(memory_type: str = "decision", memory_id: str = "m1:decision:1") -> StoredMemory:
    return StoredMemory(
        memory_id=memory_id,
        meeting_id="m1",
        memory_type=memory_type,
        text="We chose Postgres",
        confidence=0.9,
        utterance_index=1,
        content_hash="c",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        status=MemoryStatus.ACTIVE,
        speaker="Alice",
    )


def test_slugify_normalises_text() -> None:
    assert slugify("Project Atlas!") == "project-atlas"
    assert slugify("  Multi   Word  ") == "multi-word"
    assert slugify("***") == "unknown"


def test_make_id_composes_type_and_ref() -> None:
    assert GraphNode.make_id(EntityType.PROJECT, "atlas") == "project:atlas"


def test_node_for_meeting_carries_date_metadata() -> None:
    node = GraphNode.for_meeting(_meeting())
    assert node.node_id == "meeting:m1"
    assert node.node_type is EntityType.MEETING
    assert node.label == "Project Atlas Kickoff"
    assert node.metadata["date"] == "2026-01-05"


def test_node_for_meeting_without_title_or_date() -> None:
    meeting = StoredMeeting(meeting_id="m2", transcript_hash="h", created_at="2026-01-01")
    node = GraphNode.for_meeting(meeting)
    assert node.label == "m2"
    assert node.metadata == {}


def test_node_for_memory_maps_primitive_type() -> None:
    node = GraphNode.for_memory(_memory("risk", "m1:risk:1"))
    assert node.node_id == "risk:m1:risk:1"
    assert node.node_type is EntityType.RISK
    assert node.metadata["status"] == "active"
    assert node.metadata["meeting_id"] == "m1"


def test_node_for_open_loop_maps_to_memory_type() -> None:
    node = GraphNode.for_memory(_memory("open_loop", "m1:open_loop:1"))
    assert node.node_type is EntityType.MEMORY
    assert node.node_id == "memory:m1:open_loop:1"


def test_node_for_person_and_entity() -> None:
    person = GraphNode.for_person("Alice Smith")
    assert person.node_id == "person:alice-smith"
    assert person.node_type is EntityType.PERSON
    entity = GraphNode.for_entity(EntityType.TECHNOLOGY, "PostgreSQL")
    assert entity.node_id == "technology:postgresql"
    assert entity.label == "PostgreSQL"


def test_node_to_dict_roundtrip_fields() -> None:
    node = GraphNode.for_entity(EntityType.PROJECT, "Atlas", created_at="2026-01-01")
    payload = node.to_dict()
    assert payload["node_id"] == "project:atlas"
    assert payload["node_type"] == "project"
    assert payload["ref_id"] == "atlas"


def test_edge_create_is_deterministic() -> None:
    first = GraphEdge.create("a", RelationshipType.MENTIONS, "b")
    second = GraphEdge.create("a", RelationshipType.MENTIONS, "b")
    assert first.edge_id == second.edge_id
    assert first.relationship is RelationshipType.MENTIONS


def test_edge_discriminator_changes_id() -> None:
    base = GraphEdge.create("a", RelationshipType.CONNECTED_TO, "b")
    disc = GraphEdge.create("a", RelationshipType.CONNECTED_TO, "b", discriminator="m1")
    assert base.edge_id != disc.edge_id


def test_edge_to_dict() -> None:
    edge = GraphEdge.create("a", RelationshipType.BLOCKS, "b", metadata={"k": "v"})
    payload = edge.to_dict()
    assert payload["source_id"] == "a"
    assert payload["target_id"] == "b"
    assert payload["relationship"] == "blocks"
    assert payload["metadata"] == {"k": "v"}


def test_graph_path_length_and_to_dict() -> None:
    nodes = (GraphNode.for_person("A"), GraphNode.for_person("B"))
    edges = (GraphEdge.create("person:a", RelationshipType.CONNECTED_TO, "person:b"),)
    path = GraphPath(nodes=nodes, edges=edges)
    assert path.length == 1
    payload = path.to_dict()
    assert payload["length"] == 1
    assert len(payload["nodes"]) == 2  # type: ignore[arg-type]


def test_graph_query_to_dict() -> None:
    query = GraphQuery(
        node_id="project:atlas",
        node_types=frozenset({EntityType.MEETING}),
        relationships=frozenset({RelationshipType.MENTIONS}),
        depth=2,
        limit=5,
    )
    payload = query.to_dict()
    assert payload["node_id"] == "project:atlas"
    assert payload["node_types"] == ["meeting"]
    assert payload["relationships"] == ["mentions"]
    assert payload["depth"] == 2


def test_graph_result_to_dict() -> None:
    result = GraphResult(nodes=(GraphNode.for_person("A"),), edges=(), paths=())
    payload = result.to_dict()
    assert len(payload["nodes"]) == 1  # type: ignore[arg-type]
    assert payload["edges"] == []
    assert payload["paths"] == []


def test_relationship_registry_describes_every_type() -> None:
    assert set(RELATIONSHIP_REGISTRY) == set(RelationshipType)
    connected = RELATIONSHIP_REGISTRY[RelationshipType.CONNECTED_TO]
    assert isinstance(connected, GraphRelationship)
    assert connected.directed is False
    assert connected.to_dict()["label"] == "connected to"


def test_enum_str() -> None:
    assert str(EntityType.PROJECT) == "project"
    assert str(RelationshipType.MENTIONS) == "mentions"
