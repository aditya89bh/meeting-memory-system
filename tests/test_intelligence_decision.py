"""Tests for decision intelligence and the shared analysis helpers."""

from __future__ import annotations

from intelligence_helpers import load_store, make_meeting, make_memory
from meeting_memory.intelligence import InsightType, IntelligenceEngine
from meeting_memory.intelligence.analysis import (
    content_groups,
    days_between,
    insight_id,
    memory_evidence,
    recurring_groups,
    scale_severity,
    supersession_chains,
    top_counter,
)
from meeting_memory.intelligence.context import build_context
from meeting_memory.intelligence.decision import decision_insights, decision_metrics
from meeting_memory.intelligence.models import InsightSeverity
from meeting_memory.storage import MemoryStatus


def _context(meetings, memories):
    return build_context(memories, meetings)


# -- analysis helpers ---------------------------------------------------------


def test_scale_severity_thresholds() -> None:
    assert scale_severity(0, 2, 4, 6) is InsightSeverity.LOW
    assert scale_severity(2, 2, 4, 6) is InsightSeverity.MEDIUM
    assert scale_severity(4, 2, 4, 6) is InsightSeverity.HIGH
    assert scale_severity(6, 2, 4, 6) is InsightSeverity.CRITICAL


def test_days_between_and_insight_id_and_top_counter() -> None:
    assert days_between("2026-01-01", "2026-01-31") == 30
    assert days_between("bad", "2026-01-01") == 0
    assert insight_id("Decision", "Super Seded", "") == "decision-super-seded"
    assert top_counter({}) == (None, 0)
    assert top_counter({"a": 1, "b": 2}) == ("b", 2)
    assert top_counter({"a": 2, "b": 2}) == ("a", 2)


def test_content_and_recurring_groups() -> None:
    memories = [
        make_memory(
            "r1",
            "risk",
            "X",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            content_hash="h",
        ),
        make_memory(
            "r2",
            "risk",
            "X",
            meeting_id="m2",
            created_at="2026-02-01T09:00:00+00:00",
            content_hash="h",
        ),
        make_memory(
            "r3",
            "risk",
            "Y",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            content_hash="k",
        ),
    ]
    groups = content_groups(memories)
    assert set(groups) == {"h", "k"}
    recurring = recurring_groups(memories)
    assert set(recurring) == {"h"}


def test_supersession_chains_follows_and_guards_cycles() -> None:
    d0 = make_memory(
        "d0",
        "decision",
        "A",
        meeting_id="m1",
        created_at="2026-01-01T09:00:00+00:00",
        superseded_by="d1",
    )
    d1 = make_memory(
        "d1",
        "decision",
        "B",
        meeting_id="m2",
        created_at="2026-02-01T09:00:00+00:00",
        superseded_by="d2",
    )
    d2 = make_memory(
        "d2",
        "decision",
        "C",
        meeting_id="m3",
        created_at="2026-03-01T09:00:00+00:00",
        superseded_by="d1",
    )
    index = {m.memory_id: m for m in (d0, d1, d2)}
    chains = supersession_chains([d0, d1, d2], index)
    assert [m.memory_id for m in chains[0]] == ["d0", "d1", "d2"]

    single = make_memory(
        "s0", "decision", "S", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"
    )
    assert supersession_chains([single], {"s0": single}) == []


def test_memory_evidence_collects_ids() -> None:
    memories = [
        make_memory("a", "fact", "x", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"),
        make_memory("b", "fact", "y", meeting_id="m1", created_at="2026-01-01T09:01:00+00:00"),
    ]
    evidence = memory_evidence(memories, "two", value=2.0)
    assert evidence.memory_ids == ("a", "b")
    assert evidence.meeting_ids == ("m1",)


# -- decision metrics ---------------------------------------------------------


def test_decision_metrics_empty() -> None:
    context = _context([make_meeting("m1", date="2026-01-01")], [])
    assert decision_metrics(context).total == 0


def test_decision_metrics_values() -> None:
    meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-03-01"),
    ]
    memories = [
        make_memory(
            "d1",
            "decision",
            "A",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            speaker="Alice",
        ),
        make_memory(
            "d2",
            "decision",
            "B",
            meeting_id="m2",
            created_at="2026-03-01T09:00:00+00:00",
            speaker="Bob",
        ),
    ]
    metrics = decision_metrics(_context(meetings, memories))
    assert metrics.total == 2
    assert metrics.active == 2
    assert metrics.distinct_owners == 2
    assert metrics.top_owner == "Alice"
    assert metrics.density == 1.0
    assert metrics.velocity_per_week < 1.0


# -- decision insights --------------------------------------------------------


def test_decision_insights_empty() -> None:
    context = _context([make_meeting("m1", date="2026-01-01")], [])
    assert decision_insights(context) == []


def test_decision_insights_supersede_and_long_running() -> None:
    meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-02-15"),
        make_meeting("m3", date="2026-03-20"),
    ]
    memories = [
        make_memory(
            "d1",
            "decision",
            "Use Postgres",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            status=MemoryStatus.SUPERSEDED,
            superseded_by="d2",
        ),
        make_memory(
            "d2",
            "decision",
            "Use MySQL",
            meeting_id="m2",
            created_at="2026-02-15T09:00:00+00:00",
            status=MemoryStatus.SUPERSEDED,
            superseded_by="d3",
        ),
        make_memory(
            "d3", "decision", "Use SQLite", meeting_id="m3", created_at="2026-03-20T09:00:00+00:00"
        ),
    ]
    store = load_store(meetings, memories)
    report = IntelligenceEngine().analyze(store)
    types = {i.type for i in report.insights}
    assert InsightType.REPEATEDLY_SUPERSEDED_DECISION in types
    assert InsightType.LONG_RUNNING_DECISION in types
    store.close()


def test_decision_insights_revisited_and_unstable() -> None:
    meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-01-10"),
    ]
    long_text = "We should re-evaluate the rollout plan in detail " * 3
    memories = [
        make_memory(
            "q1",
            "decision",
            long_text,
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            content_hash="dup",
        ),
        make_memory(
            "q2",
            "decision",
            long_text,
            meeting_id="m2",
            created_at="2026-01-10T09:00:00+00:00",
            content_hash="dup",
        ),
        make_memory(
            "s1",
            "decision",
            "Superseded one",
            meeting_id="m1",
            created_at="2026-01-01T09:03:00+00:00",
            status=MemoryStatus.SUPERSEDED,
        ),
        make_memory(
            "s2",
            "decision",
            "Superseded two",
            meeting_id="m1",
            created_at="2026-01-01T09:04:00+00:00",
            status=MemoryStatus.SUPERSEDED,
        ),
        make_memory(
            "s3",
            "decision",
            "Superseded three",
            meeting_id="m1",
            created_at="2026-01-01T09:05:00+00:00",
            status=MemoryStatus.SUPERSEDED,
        ),
    ]
    context = _context(meetings, memories)
    insights = decision_insights(context)
    types = {i.type for i in insights}
    assert InsightType.REVISITED_DECISION in types
    assert InsightType.UNSTABLE_DECISIONS in types
    # The revisited title quotes truncated text.
    revisited = next(i for i in insights if i.type is InsightType.REVISITED_DECISION)
    assert "\u2026" in revisited.detail


def test_decision_not_unstable_when_few_or_stable() -> None:
    meetings = [make_meeting("m1", date="2026-01-01")]
    stable = [
        make_memory(
            f"d{i}", "decision", f"D{i}", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"
        )
        for i in range(4)
    ]
    insights = decision_insights(_context(meetings, stable))
    assert all(i.type is not InsightType.UNSTABLE_DECISIONS for i in insights)
