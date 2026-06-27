"""Unit tests for entity extraction, relationship extraction, building, and export."""

from __future__ import annotations

from meeting_memory.graph import (
    EntityType,
    RelationshipType,
    SQLiteGraphStore,
    build_graph,
    cross_meeting_edges,
    detect_entities,
    export_graph,
    extract_entities,
    to_dot,
    to_json,
    to_mermaid,
)
from meeting_memory.graph.entities import EntityVocabulary
from meeting_memory.graph.linking import (
    MeetingRecord,
    MemoryRecord,
    collaboration_edges,
    repeated_content_edges,
    resolves_edges,
)
from meeting_memory.graph.relationships import meeting_relationships
from meeting_memory.storage import MemoryStatus, SQLiteMemoryStore, StoredMeeting, StoredMemory


def _meeting(meeting_id: str = "m1", title: str = "Project Atlas Kickoff") -> StoredMeeting:
    return StoredMeeting(
        meeting_id=meeting_id,
        transcript_hash=f"h-{meeting_id}",
        created_at="2026-01-01T00:00:00+00:00",
        title=title,
        date="2026-01-05",
        participants=("Alice", "Bob"),
    )


def _memory(
    memory_type: str,
    memory_id: str,
    text: str,
    *,
    meeting_id: str = "m1",
    speaker: str = "Alice",
    metadata: dict[str, str] | None = None,
    content_hash: str | None = None,
    superseded_by: str | None = None,
) -> StoredMemory:
    return StoredMemory(
        memory_id=memory_id,
        meeting_id=meeting_id,
        memory_type=memory_type,
        text=text,
        confidence=0.9,
        utterance_index=1,
        content_hash=content_hash or memory_id,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        status=MemoryStatus.ACTIVE,
        speaker=speaker,
        metadata=metadata or {},
        superseded_by=superseded_by,
    )


# -- entity extraction --------------------------------------------------------


def test_detect_entities_finds_technology_project_customer() -> None:
    vocab = EntityVocabulary(customers=frozenset({"Acme"}))
    found = detect_entities("We use Postgres for Project Atlas with customer Acme.", vocab)
    assert (EntityType.TECHNOLOGY, "postgres") in found
    assert (EntityType.PROJECT, "Atlas") in found
    assert (EntityType.CUSTOMER, "Acme") in found


def test_detect_entities_documents_and_vendor() -> None:
    found = detect_entities("See the runbook.md and vendor Globex.", EntityVocabulary())
    kinds = {kind for kind, _ in found}
    assert EntityType.DOCUMENT in kinds
    assert EntityType.VENDOR in kinds


def test_extract_entities_builds_nodes_and_mentions() -> None:
    meeting = _meeting()
    memories = [
        _memory("decision", "m1:decision:1", "We chose Postgres for Project Atlas."),
        _memory("fact", "m1:fact:1", "Nothing notable here."),
    ]
    extraction = extract_entities(meeting, memories)
    assert "technology:postgres" in extraction.nodes
    assert "project:atlas" in extraction.nodes
    assert "technology:postgres" in extraction.memory_mentions["m1:decision:1"]
    assert "m1:fact:1" not in extraction.memory_mentions
    assert "project:atlas" in extraction.meeting_mentions


# -- relationship extraction --------------------------------------------------


def test_meeting_relationships_structural_and_semantic() -> None:
    meeting = _meeting()
    memories = [
        _memory("decision", "m1:decision:1", "We chose Postgres for Project Atlas."),
        _memory("risk", "m1:risk:1", "Risk to Project Atlas from load.", speaker="Bob"),
        _memory(
            "commitment",
            "m1:commitment:1",
            "I will ship it.",
            metadata={"owner": "Bob"},
        ),
        _memory("fact", "m1:fact:1", "Customer Acme drives usage."),
    ]
    vocab = EntityVocabulary(customers=frozenset({"Acme"}))
    extraction = extract_entities(meeting, memories, vocab)
    edges = meeting_relationships(meeting, memories, extraction)
    rels = {(e.source_id, e.relationship, e.target_id) for e in edges}
    assert ("decision:m1:decision:1", RelationshipType.DISCUSSED_IN, "meeting:m1") in rels
    assert ("decision:m1:decision:1", RelationshipType.OWNED_BY, "person:alice") in rels
    assert ("commitment:m1:commitment:1", RelationshipType.ASSIGNED_TO, "person:bob") in rels
    assert ("decision:m1:decision:1", RelationshipType.RELATES_TO, "project:atlas") in rels
    assert ("risk:m1:risk:1", RelationshipType.BLOCKS, "project:atlas") in rels
    assert ("fact:m1:fact:1", RelationshipType.REFERENCES, "customer:acme") in rels
    assert ("project:atlas", RelationshipType.DEPENDS_ON, "technology:postgres") in rels
    assert ("meeting:m1", RelationshipType.MENTIONS, "person:alice") in rels


def test_meeting_relationships_commitment_without_owner_or_speaker() -> None:
    meeting = _meeting()
    memories = [_memory("commitment", "m1:commitment:1", "Someone will do it.", speaker=None)]  # type: ignore[arg-type]
    edges = meeting_relationships(meeting, memories, extract_entities(meeting, memories))
    rels = {e.relationship for e in edges}
    assert RelationshipType.ASSIGNED_TO not in rels


def test_meeting_relationships_commitment_falls_back_to_speaker() -> None:
    meeting = _meeting()
    memories = [_memory("commitment", "m1:commitment:1", "I will do it.", speaker="Carol")]
    edges = meeting_relationships(meeting, memories, extract_entities(meeting, memories))
    rels = {(e.source_id, e.relationship, e.target_id) for e in edges}
    assert ("commitment:m1:commitment:1", RelationshipType.ASSIGNED_TO, "person:carol") in rels


def test_meeting_relationships_handles_memory_without_speaker() -> None:
    meeting = _meeting()
    memories = [_memory("fact", "m1:fact:1", "Nothing here.", speaker=None)]  # type: ignore[arg-type]
    edges = meeting_relationships(meeting, memories, extract_entities(meeting, memories))
    rels = {e.relationship for e in edges}
    assert RelationshipType.OWNED_BY not in rels  # no speaker -> no owner edge
    assert RelationshipType.DISCUSSED_IN in rels


def test_shared_entity_links_skip_when_no_overlap_or_no_entities() -> None:
    meeting = _meeting()
    memories = [
        _memory("decision", "m1:decision:1", "We chose Postgres for Project Atlas."),
        _memory("question", "m1:question:1", "An unrelated question with no entities."),
        _memory("assumption", "m1:assumption:1", "Assuming Project Beta is fine."),
    ]
    extraction = extract_entities(meeting, memories)
    edges = meeting_relationships(meeting, memories, extraction)
    rels = {(e.source_id, e.relationship, e.target_id) for e in edges}
    # Question has no detected entity -> no RELATES_TO link from it.
    question_rels = [e for e in rels if e[0].startswith("question:")]
    assert not any(e[1] is RelationshipType.RELATES_TO for e in question_rels)
    # Assumption mentions Beta, decision mentions Atlas -> no overlap, no SUPPORTS link.
    assert not any(e[1] is RelationshipType.SUPPORTS for e in rels)


def test_shared_entity_links_question_and_assumption_to_decision() -> None:
    meeting = _meeting()
    memories = [
        _memory("decision", "m1:decision:1", "We chose Postgres for Project Atlas."),
        _memory("question", "m1:question:1", "Is Project Atlas on track?"),
        _memory("assumption", "m1:assumption:1", "Assuming Project Atlas stays funded."),
    ]
    extraction = extract_entities(meeting, memories)
    edges = meeting_relationships(meeting, memories, extraction)
    rels = {(e.source_id, e.relationship, e.target_id) for e in edges}
    assert ("question:m1:question:1", RelationshipType.RELATES_TO, "decision:m1:decision:1") in rels
    assert (
        "assumption:m1:assumption:1",
        RelationshipType.SUPPORTS,
        "decision:m1:decision:1",
    ) in rels


# -- cross-meeting linking ----------------------------------------------------


def test_repeated_content_edges_chain_across_meetings() -> None:
    records = [
        MemoryRecord(
            _memory("risk", "m1:risk:1", "Same risk", meeting_id="m1", content_hash="x"),
            "risk:m1:risk:1",
            "2026-01-05",
            frozenset(),
        ),
        MemoryRecord(
            _memory("risk", "m2:risk:1", "Same risk", meeting_id="m2", content_hash="x"),
            "risk:m2:risk:1",
            "2026-01-12",
            frozenset(),
        ),
    ]
    edges = repeated_content_edges(records)
    assert len(edges) == 1
    assert edges[0].source_id == "risk:m2:risk:1"
    assert edges[0].target_id == "risk:m1:risk:1"
    assert edges[0].relationship is RelationshipType.CONNECTED_TO


def test_repeated_content_ignored_within_single_meeting() -> None:
    records = [
        MemoryRecord(
            _memory("risk", "m1:risk:1", "Same", meeting_id="m1", content_hash="x"),
            "risk:m1:risk:1",
            "2026-01-05",
            frozenset(),
        ),
        MemoryRecord(
            _memory("risk", "m1:risk:2", "Same", meeting_id="m1", content_hash="x"),
            "risk:m1:risk:2",
            "2026-01-05",
            frozenset(),
        ),
    ]
    assert repeated_content_edges(records) == []


def test_resolves_edges_links_commitment_to_earlier_issue() -> None:
    records = [
        MemoryRecord(
            _memory("risk", "m1:risk:1", "Risk", meeting_id="m1"),
            "risk:m1:risk:1",
            "2026-01-05",
            frozenset({"project:atlas"}),
        ),
        MemoryRecord(
            _memory("commitment", "m2:commitment:1", "Fix it", meeting_id="m2"),
            "commitment:m2:commitment:1",
            "2026-01-12",
            frozenset({"project:atlas"}),
        ),
    ]
    edges = resolves_edges(records)
    assert len(edges) == 1
    assert edges[0].source_id == "commitment:m2:commitment:1"
    assert edges[0].target_id == "risk:m1:risk:1"
    assert edges[0].relationship is RelationshipType.RESOLVES


def test_repeated_content_skips_same_meeting_pair_within_group() -> None:
    # A three-record group spanning two meetings; the adjacent same-meeting pair
    # is skipped, the cross-meeting pair is linked.
    records = [
        MemoryRecord(
            _memory("risk", "m1:risk:1", "Same", meeting_id="m1", content_hash="x"),
            "risk:m1:risk:1",
            "2026-01-05",
            frozenset(),
        ),
        MemoryRecord(
            _memory("risk", "m1:risk:2", "Same", meeting_id="m1", content_hash="x"),
            "risk:m1:risk:2",
            "2026-01-05",
            frozenset(),
        ),
        MemoryRecord(
            _memory("risk", "m2:risk:1", "Same", meeting_id="m2", content_hash="x"),
            "risk:m2:risk:1",
            "2026-01-12",
            frozenset(),
        ),
    ]
    edges = repeated_content_edges(records)
    pairs = {(edge.source_id, edge.target_id) for edge in edges}
    assert ("risk:m2:risk:1", "risk:m1:risk:2") in pairs
    assert ("risk:m1:risk:2", "risk:m1:risk:1") not in pairs


def test_resolves_edges_skip_commitment_without_entities() -> None:
    records = [
        MemoryRecord(
            _memory("risk", "m1:risk:1", "Risk"),
            "risk:m1:risk:1",
            "2026-01-05",
            frozenset({"project:atlas"}),
        ),
        MemoryRecord(
            _memory("commitment", "m1:commitment:1", "Fix"),
            "commitment:m1:commitment:1",
            "2026-01-05",
            frozenset(),
        ),
    ]
    assert resolves_edges(records) == []


def test_resolves_edges_skip_identical_memory_id() -> None:
    shared = MemoryRecord(
        _memory("commitment", "dup", "Fix"),
        "commitment:dup",
        "2026-01-05",
        frozenset({"project:atlas"}),
    )
    issue = MemoryRecord(
        _memory("risk", "dup", "Risk"),
        "risk:dup",
        "2026-01-05",
        frozenset({"project:atlas"}),
    )
    assert resolves_edges([shared, issue]) == []


def test_resolves_edges_require_shared_entity_and_ordering() -> None:
    # No shared entity.
    no_overlap = [
        MemoryRecord(
            _memory("risk", "m1:risk:1", "Risk"),
            "risk:m1:risk:1",
            "2026-01-05",
            frozenset({"project:atlas"}),
        ),
        MemoryRecord(
            _memory("commitment", "m1:commitment:1", "Fix"),
            "commitment:m1:commitment:1",
            "2026-01-05",
            frozenset({"project:beta"}),
        ),
    ]
    assert resolves_edges(no_overlap) == []
    # Commitment earlier than the risk -> not a resolution.
    wrong_order = [
        MemoryRecord(
            _memory("risk", "m2:risk:1", "Risk", meeting_id="m2"),
            "risk:m2:risk:1",
            "2026-01-12",
            frozenset({"project:atlas"}),
        ),
        MemoryRecord(
            _memory("commitment", "m1:commitment:1", "Fix", meeting_id="m1"),
            "commitment:m1:commitment:1",
            "2026-01-05",
            frozenset({"project:atlas"}),
        ),
    ]
    assert resolves_edges(wrong_order) == []


def test_collaboration_edges_one_per_meeting() -> None:
    meetings = [
        MeetingRecord("m1", "2026-01-05", ("Alice", "Bob")),
        MeetingRecord("m2", "2026-01-12", ("Alice", "Bob")),
    ]
    edges = collaboration_edges(meetings)
    assert len(edges) == 2  # one per shared meeting
    assert all(edge.relationship is RelationshipType.CONNECTED_TO for edge in edges)
    assert {edge.metadata["meeting_id"] for edge in edges} == {"m1", "m2"}


def test_cross_meeting_edges_combines_sources() -> None:
    records = [
        MemoryRecord(
            _memory("risk", "m1:risk:1", "Same", meeting_id="m1", content_hash="x"),
            "risk:m1:risk:1",
            "2026-01-05",
            frozenset({"project:atlas"}),
        ),
        MemoryRecord(
            _memory("risk", "m2:risk:1", "Same", meeting_id="m2", content_hash="x"),
            "risk:m2:risk:1",
            "2026-01-12",
            frozenset({"project:atlas"}),
        ),
    ]
    meetings = [MeetingRecord("m1", "2026-01-05", ("Alice", "Bob"))]
    edges = cross_meeting_edges(records, meetings)
    rels = {edge.relationship for edge in edges}
    assert RelationshipType.CONNECTED_TO in rels


# -- builder ------------------------------------------------------------------


def test_build_graph_is_idempotent_and_links_supersedes() -> None:
    store = SQLiteMemoryStore(":memory:")
    store.save_meeting(_meeting())
    store.save(_memory("decision", "m1:decision:1", "We chose Postgres for Project Atlas."))
    store.save(
        _memory(
            "decision",
            "m1:decision:2",
            "We switched Project Atlas to Redis.",
            superseded_by=None,
        )
    )
    # decision:1 superseded by decision:2
    store.supersede("m1:decision:1", "m1:decision:2")

    graph = SQLiteGraphStore(":memory:")
    result = build_graph(store, graph)
    assert result.nodes_added > 0
    assert result.node_total == graph.count_nodes()
    supersedes = graph.list_edges(relationships=frozenset({RelationshipType.SUPERSEDES}))
    assert ("decision:m1:decision:2", "decision:m1:decision:1") in {
        (edge.source_id, edge.target_id) for edge in supersedes
    }
    again = build_graph(store, graph)
    assert again.nodes_added == 0
    assert again.edges_added == 0
    store.close()
    graph.close()


def test_graph_build_result_summary_and_dict() -> None:
    from meeting_memory.graph import GraphBuildResult

    result = GraphBuildResult(nodes_added=3, edges_added=5, node_total=10, edge_total=20)
    assert any("10 nodes" in line for line in result.summary_lines())
    payload = result.to_dict()
    assert payload == {
        "nodes_added": 3,
        "edges_added": 5,
        "node_total": 10,
        "edge_total": 20,
    }


# -- export -------------------------------------------------------------------


def _export_nodes_edges() -> tuple[list, list]:  # type: ignore[type-arg]
    from meeting_memory.graph import GraphEdge, GraphNode

    nodes = [
        GraphNode.for_entity(EntityType.PROJECT, "Atlas"),
        GraphNode.for_person('Bob "B"'),
    ]
    edges = [
        GraphEdge.create("person:bob-b", RelationshipType.MENTIONS, "project:atlas"),
        GraphEdge.create("person:bob-b", RelationshipType.MENTIONS, "missing:node"),
    ]
    return nodes, edges


def test_to_json_sorts_nodes_and_edges() -> None:
    nodes, edges = _export_nodes_edges()
    payload = to_json(nodes, edges)
    node_ids = [node["node_id"] for node in payload["nodes"]]  # type: ignore[index]
    assert node_ids == sorted(node_ids)


def test_to_mermaid_skips_dangling_edges_and_escapes() -> None:
    nodes, edges = _export_nodes_edges()
    text = to_mermaid(nodes, edges)
    assert text.startswith("graph TD")
    assert "missing:node" not in text  # dangling edge target skipped
    assert "Bob 'B'" in text  # double quotes in label are replaced for mermaid


def test_to_dot_escapes_quotes() -> None:
    nodes, edges = _export_nodes_edges()
    text = to_dot(nodes, edges)
    assert text.startswith("digraph memory_graph")
    assert '\\"' in text  # the quote in label 'Bob "B"' is escaped


def test_export_graph_dispatch_and_unknown_format() -> None:
    nodes, edges = _export_nodes_edges()
    assert isinstance(export_graph(nodes, edges, "json"), dict)
    assert isinstance(export_graph(nodes, edges, "mermaid"), str)
    assert isinstance(export_graph(nodes, edges, "dot"), str)
    try:
        export_graph(nodes, edges, "xml")
    except ValueError as exc:
        assert "unknown export format" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_long_label_is_truncated_in_export() -> None:
    from meeting_memory.graph import GraphNode

    node = GraphNode(
        node_id="decision:x",
        node_type=EntityType.DECISION,
        label="word " * 40,
        ref_id="x",
    )
    text = to_dot([node], [])
    assert "…" in text
