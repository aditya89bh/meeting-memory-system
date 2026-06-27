"""Tests for commitment, risk, meeting metrics and engine score helpers."""

from __future__ import annotations

from intelligence_helpers import load_store, make_meeting, make_memory
from meeting_memory.graph import SQLiteGraphStore
from meeting_memory.intelligence import InsightType, IntelligenceEngine
from meeting_memory.intelligence.analysis import person_metrics, project_metrics
from meeting_memory.intelligence.commitment import (
    _is_overdue,
    commitment_insights,
    commitment_metrics,
)
from meeting_memory.intelligence.context import build_context
from meeting_memory.intelligence.engine import (
    _avg_resolution_days,
    _collaboration_score,
    _first,
    _reuse_scores,
    _timestamp_days,
)
from meeting_memory.intelligence.health import meeting_metrics
from meeting_memory.intelligence.models import InsightSeverity
from meeting_memory.intelligence.registry import ProviderSet
from meeting_memory.intelligence.risk import risk_insights, risk_metrics
from meeting_memory.storage import MemoryStatus


def _context(meetings, memories):
    return build_context(memories, meetings)


# -- commitments --------------------------------------------------------------


def test_is_overdue_branches() -> None:
    base = {"meeting_id": "m1", "created_at": "2026-01-01T09:00:00+00:00"}
    active_due = make_memory("c", "commitment", "x", metadata={"due": "2026-01-01"}, **base)
    assert _is_overdue(active_due, "2026-02-01") == 31
    assert _is_overdue(active_due, "2025-12-01") == 0
    no_due = make_memory("c2", "commitment", "x", **base)
    assert _is_overdue(no_due, "2026-02-01") == 0
    bad_due = make_memory("c3", "commitment", "x", metadata={"due": "soon"}, **base)
    assert _is_overdue(bad_due, "2026-02-01") == 0
    resolved = make_memory(
        "c4",
        "commitment",
        "x",
        metadata={"due": "2026-01-01"},
        status=MemoryStatus.RESOLVED,
        **base,
    )
    assert _is_overdue(resolved, "2026-02-01") == 0


def test_commitment_metrics_empty() -> None:
    assert commitment_metrics(_context([make_meeting("m1", date="2026-01-01")], [])).total == 0


def test_commitment_metrics_values() -> None:
    meetings = [make_meeting("m1", date="2026-01-01"), make_meeting("m2", date="2026-03-01")]
    memories = [
        make_memory(
            "c1",
            "commitment",
            "spec",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            metadata={"owner": "Alice", "due": "2026-01-15"},
        ),
        make_memory(
            "c2",
            "commitment",
            "ci",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            metadata={"owner": "Alice"},
        ),
        make_memory(
            "c3",
            "commitment",
            "done",
            meeting_id="m1",
            created_at="2026-01-01T09:02:00+00:00",
            status=MemoryStatus.RESOLVED,
        ),
    ]
    metrics = commitment_metrics(_context(meetings, memories))
    assert metrics.total == 3
    assert metrics.resolved == 1
    assert metrics.open == 2
    assert metrics.overdue == 1
    assert metrics.top_owner == "Alice"
    assert metrics.top_owner_open == 2
    assert metrics.avg_open_age_days > 0


def test_commitment_insights_overload_overdue_aging() -> None:
    meetings = [make_meeting("m1", date="2026-01-01"), make_meeting("m2", date="2026-03-01")]
    memories = [
        make_memory(
            "c1",
            "commitment",
            "a",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            metadata={"owner": "Bob", "due": "2026-01-15"},
        ),
        make_memory(
            "c2",
            "commitment",
            "b",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            metadata={"owner": "Bob"},
        ),
        make_memory(
            "c3",
            "commitment",
            "c",
            meeting_id="m1",
            created_at="2026-01-01T09:02:00+00:00",
            metadata={"owner": "Bob"},
        ),
    ]
    insights = commitment_insights(_context(meetings, memories))
    types = {i.type for i in insights}
    assert InsightType.OPEN_COMMITMENT_OVERLOAD in types
    assert InsightType.OVERDUE_COMMITMENT in types
    assert InsightType.AGING_COMMITMENT in types


def test_commitment_insights_empty() -> None:
    assert commitment_insights(_context([make_meeting("m1", date="2026-01-01")], [])) == []


def test_commitment_low_resolution_severities() -> None:
    meetings = [make_meeting("m1", date="2026-01-01")]
    zero = [
        make_memory(
            f"c{i}",
            "commitment",
            f"c{i}",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            speaker=None,
        )
        for i in range(5)
    ]
    low = next(
        i
        for i in commitment_insights(_context(meetings, zero))
        if i.type is InsightType.LOW_COMMITMENT_RESOLUTION
    )
    assert low.severity is InsightSeverity.HIGH

    mixed = [
        make_memory(
            "r1",
            "commitment",
            "r1",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            status=MemoryStatus.RESOLVED,
        ),
        make_memory(
            "r2",
            "commitment",
            "r2",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            status=MemoryStatus.RESOLVED,
        ),
        make_memory(
            "o1", "commitment", "o1", meeting_id="m1", created_at="2026-01-01T09:02:00+00:00"
        ),
        make_memory(
            "o2", "commitment", "o2", meeting_id="m1", created_at="2026-01-01T09:03:00+00:00"
        ),
    ]
    assert all(
        i.type is not InsightType.LOW_COMMITMENT_RESOLUTION
        for i in commitment_insights(_context(meetings, mixed))
    )


# -- risks --------------------------------------------------------------------


def test_risk_metrics_empty_and_no_graph() -> None:
    context = _context([make_meeting("m1", date="2026-01-01")], [])
    assert risk_metrics(context).total == 0
    memories = [
        make_memory("r1", "risk", "X", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"),
    ]
    metrics = risk_metrics(_context([make_meeting("m1", date="2026-01-01")], memories))
    assert metrics.total == 1
    assert metrics.hotspot_project is None


def test_risk_insights_recurring_unresolved_and_hotspot() -> None:
    meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-02-15"),
        make_meeting("m3", date="2026-04-01"),
    ]
    memories = [
        make_memory(
            "r1",
            "risk",
            "Project Atlas may slip the deadline",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            content_hash="atlas",
        ),
        make_memory(
            "r2",
            "risk",
            "Project Atlas may slip the deadline",
            meeting_id="m2",
            created_at="2026-02-15T09:00:00+00:00",
            content_hash="atlas",
        ),
        make_memory(
            "r3",
            "risk",
            "Project Atlas may slip the deadline",
            meeting_id="m3",
            created_at="2026-04-01T09:00:00+00:00",
            content_hash="atlas",
        ),
    ]
    store = load_store(meetings, memories)
    graph = SQLiteGraphStore(":memory:")
    report = IntelligenceEngine().analyze(store, graph)
    types = {i.type for i in report.insights}
    assert InsightType.RECURRING_RISK in types
    assert InsightType.LONG_LIVED_RISK in types
    assert InsightType.UNRESOLVED_RISK in types
    assert InsightType.RISK_HOTSPOT in types
    assert InsightType.PROJECT_BLOCKER in types
    rmetrics = risk_metrics(build_context(store.list(), store.list_meetings(), graph=graph))
    assert rmetrics.hotspot_project == "Atlas"
    assert rmetrics.max_recurrence == 3
    graph.close()
    store.close()


def test_risk_insights_empty_and_no_graph_hotspot() -> None:
    assert risk_insights(_context([make_meeting("m1", date="2026-01-01")], [])) == []
    memories = [
        make_memory("r1", "risk", "X", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"),
    ]
    insights = risk_insights(_context([make_meeting("m1", date="2026-01-01")], memories))
    assert all(i.type is not InsightType.RISK_HOTSPOT for i in insights)


# -- meeting metrics ----------------------------------------------------------


def test_meeting_metrics_empty_and_values() -> None:
    empty = meeting_metrics(_context([], []))
    assert empty.total_meetings == 0
    meetings = [make_meeting("m1", date="2026-01-01"), make_meeting("m2", date="2026-02-01")]
    memories = [
        make_memory("d1", "decision", "D", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"),
        make_memory(
            "c1", "commitment", "C", meeting_id="m1", created_at="2026-01-01T09:01:00+00:00"
        ),
        make_memory(
            "f1",
            "fact",
            "shared",
            meeting_id="m1",
            created_at="2026-01-01T09:02:00+00:00",
            content_hash="s",
        ),
        make_memory(
            "f2",
            "fact",
            "shared",
            meeting_id="m2",
            created_at="2026-02-01T09:02:00+00:00",
            content_hash="s",
        ),
    ]
    metrics = meeting_metrics(_context(meetings, memories))
    assert metrics.total_meetings == 2
    assert metrics.productivity == 1.0
    assert metrics.repeated_discussion_rate > 0


# -- entity metrics -----------------------------------------------------------


def test_project_metrics_requires_graph_and_person_metrics() -> None:
    meetings = [make_meeting("m1", date="2026-01-01", participants=("Alice", "Bob"))]
    memories = [
        make_memory(
            "d1",
            "decision",
            "D",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            speaker="Alice",
        ),
        make_memory(
            "c1",
            "commitment",
            "C",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            metadata={"owner": "Bob"},
        ),
    ]
    context = _context(meetings, memories)
    assert project_metrics(context) == []
    people = {p.name: p for p in person_metrics(context)}
    assert people["Alice"].decisions_owned == 1
    assert people["Bob"].open_commitments == 1
    assert people["Alice"].meetings_attended == 1


# -- engine score helpers -----------------------------------------------------


def test_reuse_collaboration_resolution_helpers() -> None:
    empty = _context([], [])
    assert _reuse_scores(empty) == (0.0, 0.0)
    assert _collaboration_score(empty) == 0.0
    assert _avg_resolution_days(empty) == 0.0

    solo = _context([make_meeting("m1", date="2026-01-01", participants=("Alice",))], [])
    assert _collaboration_score(solo) == 0.0

    duo = _context([make_meeting("m1", date="2026-01-01", participants=("Alice", "Bob"))], [])
    assert _collaboration_score(duo) == 1.0

    resolved = make_memory(
        "c1",
        "commitment",
        "x",
        meeting_id="m1",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-11T00:00:00+00:00",
        status=MemoryStatus.RESOLVED,
    )
    bad = make_memory(
        "c2",
        "commitment",
        "y",
        meeting_id="m1",
        created_at="bad",
        updated_at="bad",
        status=MemoryStatus.ARCHIVED,
    )
    context = _context([make_meeting("m1", date="2026-01-01")], [resolved, bad])
    assert _avg_resolution_days(context) == 10.0
    assert _timestamp_days("bad", "bad") is None


def test_first_returns_none_when_absent() -> None:
    assert _first({}, int) is None


def test_run_health_defaults_with_empty_providers() -> None:
    store = load_store([make_meeting("m1", date="2026-01-01")], [])
    engine = IntelligenceEngine(ProviderSet())
    report = engine.analyze(store)
    assert report.health.decision.total == 0
    assert report.health.meeting.total_meetings == 0
    store.close()
