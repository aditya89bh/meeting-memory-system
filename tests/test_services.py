"""Tests for the shared service layer (Phase 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_helpers import EXAMPLES_HISTORY, seed_db
from meeting_memory.exceptions import (
    MeetingNotFoundError,
    MemoryNotFoundError,
    PipelineConfigError,
)
from meeting_memory.intelligence import AnalysisFilters
from meeting_memory.retrieval import RetrievalQuery
from meeting_memory.services import (
    AutomationService,
    ExportService,
    GraphService,
    IntelligenceService,
    MeetingService,
    MemoryService,
    RetrievalService,
)
from meeting_memory.services.automation import jobs_path, logs_path


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """A seeded SQLite database."""
    path = tmp_path / "atlas.db"
    seed_db(path)
    return path


# --- meetings ------------------------------------------------------------


def test_meeting_service_import_content_and_stats(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    service = MeetingService(path)
    result = service.import_content("Alice: We decided to ship the beta.\n", "text")
    assert result.meetings_imported == 1
    stats = service.stats()
    assert stats.meetings == 1
    assert stats.memories >= 1
    assert sum(stats.by_type.values()) == stats.memories


def test_meeting_service_import_dry_run(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    service = MeetingService(path)
    result = service.import_path(EXAMPLES_HISTORY, recursive=True, dry_run=True)
    assert result.dry_run is True
    assert service.count_meetings() == 0


def test_meeting_service_list_and_get(db: Path) -> None:
    service = MeetingService(db)
    assert service.count_meetings() == 4
    meetings = service.list_meetings(limit=2)
    assert len(meetings) == 2
    page = service.list_meetings(limit=2, offset=2)
    assert page and page[0].meeting_id != meetings[0].meeting_id
    fetched = service.get_meeting(meetings[0].meeting_id)
    assert fetched.meeting_id == meetings[0].meeting_id


def test_meeting_service_get_missing(db: Path) -> None:
    with pytest.raises(MeetingNotFoundError):
        MeetingService(db).get_meeting("nope")


# --- memories ------------------------------------------------------------


def test_memory_service_query_and_get(db: Path) -> None:
    service = MemoryService(db)
    all_memories = service.list_memories()
    assert all_memories
    assert service.count() == len(all_memories)
    decisions = service.list_memories(memory_types=frozenset({"decision"}))
    assert all(memory.memory_type == "decision" for memory in decisions)
    one = service.get_memory(all_memories[0].memory_id)
    assert one.memory_id == all_memories[0].memory_id


def test_memory_service_get_missing(db: Path) -> None:
    with pytest.raises(MemoryNotFoundError):
        MemoryService(db).get_memory("nope")


# --- retrieval -----------------------------------------------------------


def test_retrieval_service_search_timeline_explain(db: Path) -> None:
    service = RetrievalService(db)
    hits = service.search(RetrievalQuery(text="postgres"))
    assert hits.ranked
    timeline = service.timeline(RetrievalQuery(text="postgres"))
    assert timeline.ranked
    memory_id = hits.ranked[0].memory.memory_id
    explained = service.explain(memory_id, context_size=1)
    assert explained.memory.memory_id == memory_id
    payload = explained.to_dict()
    assert "explanation" in payload and "context" in payload


# --- graph ---------------------------------------------------------------


def test_graph_service_summary_neighbors_path_export(db: Path) -> None:
    service = GraphService(db)
    summary = service.summary(limit=5)
    assert summary.nodes > 0
    assert len(summary.listed) <= 5
    node_id = summary.listed[0].node_id
    neighborhood = service.neighbors(node_id, depth=2)
    assert neighborhood.node.node_id == node_id
    related = [n for n in neighborhood.result.nodes if n.node_id != node_id]
    if related:
        found = service.path(node_id, related[0].node_id, max_depth=4)
        assert found is not None and found.length >= 1
    rendered = service.export("json", limit=5)
    assert isinstance(rendered, dict)
    mermaid = service.export("mermaid", limit=5)
    assert isinstance(mermaid, str)


def test_graph_service_path_absent(db: Path) -> None:
    service = GraphService(db)
    nodes = service.summary().listed
    # A path from a node to itself with no self-loop yields a zero-length path or none.
    found = service.path(nodes[0].node_id, nodes[0].node_id, max_depth=1)
    assert found is None or found.length == 0


# --- intelligence --------------------------------------------------------


def test_intelligence_service(db: Path) -> None:
    service = IntelligenceService(db)
    report = service.report(AnalysisFilters())
    assert report.insights or report.recommendations
    insights = service.insights(limit=1)
    assert len(insights) <= 1
    typed = service.insights(types=frozenset({"recurring_risk"}))
    assert all(insight.type.value == "recurring_risk" for insight in typed)
    health = service.metrics()
    assert 0.0 <= health.overall <= 1.0
    recs = service.recommendations(limit=1)
    assert len(recs) <= 1
    rendered = service.render(report, "markdown")
    assert rendered.startswith("#")


# --- export --------------------------------------------------------------


def test_export_service_string_and_file(db: Path, tmp_path: Path) -> None:
    service = ExportService(db)
    result = service.export("json", dry_run=True)
    assert result.dry_run is True
    string_result = service.export("markdown")
    assert string_result.content
    out = tmp_path / "report.md"
    file_result = service.export("markdown", destination=out)
    assert out.exists()
    assert file_result.destination is not None
    assert "markdown" in ExportService.formats()


# --- automation ----------------------------------------------------------


def test_automation_service_run_and_history(db: Path) -> None:
    service = AutomationService(db)
    result = service.run_config(
        {"name": "report", "steps": [{"type": "graph"}, {"type": "intelligence"}]}
    )
    assert result.status.value == "success"
    assert jobs_path(db).exists()
    assert logs_path(db).exists()
    jobs = service.jobs()
    assert len(jobs) == 1
    logs = service.logs()
    assert logs
    filtered = service.logs(correlation_id=result.correlation_id)
    assert filtered


def test_automation_service_run_file(db: Path, tmp_path: Path) -> None:
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "name: file-run\nsteps:\n  - type: graph\n  - type: intelligence\n",
        encoding="utf-8",
    )
    job = AutomationService.load(config)
    assert job.name == "file-run"
    result = AutomationService(db).run_file(config, dry_run=True)
    assert result.dry_run is True


def test_automation_service_invalid_config(db: Path) -> None:
    with pytest.raises(PipelineConfigError):
        AutomationService(db).run_config({"name": "bad", "steps": [{"type": "export"}]})
