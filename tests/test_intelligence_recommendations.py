"""Tests for the recommendation engine and report rendering."""

from __future__ import annotations

import json

import pytest

from intelligence_helpers import load_store, make_meeting, make_memory
from meeting_memory.intelligence import IntelligenceEngine
from meeting_memory.intelligence.context import build_context
from meeting_memory.intelligence.models import (
    CommitmentMetrics,
    DecisionMetrics,
    Insight,
    InsightCategory,
    InsightEvidence,
    InsightReport,
    InsightSeverity,
    InsightType,
    MeetingMetrics,
    OrganizationalHealth,
    PersonMetrics,
    ProjectMetrics,
    RecommendationPriority,
    RiskMetrics,
)
from meeting_memory.intelligence.recommendations import (
    cadence_recommendation,
    recommendations_from,
)
from meeting_memory.intelligence.report import (
    REPORT_FORMATS,
    render_report,
    to_json,
    to_markdown,
    to_text,
)
from meeting_memory.storage import MemoryStatus


def _insight(
    insight_type: InsightType,
    category: InsightCategory,
    severity: InsightSeverity,
) -> Insight:
    evidence = InsightEvidence(description="e", memory_ids=("m1", "m1", "m2"))
    return Insight(
        insight_id="i1",
        type=insight_type,
        category=category,
        severity=severity,
        title="t",
        detail="d",
        evidence=(evidence,),
    )


def test_recommendations_from_maps_and_dedupes() -> None:
    insight = _insight(
        InsightType.OVERDUE_COMMITMENT, InsightCategory.COMMITMENT, InsightSeverity.CRITICAL
    )
    recs = recommendations_from([insight])
    assert len(recs) == 1
    assert recs[0].priority is RecommendationPriority.URGENT
    assert recs[0].related_memory_ids == ("m1", "m2")


def test_recommendations_from_skips_unmapped_types() -> None:
    insight = _insight(
        InsightType.REPEATED_DISCUSSION, InsightCategory.MEETING, InsightSeverity.LOW
    )
    assert recommendations_from([insight]) == []


def test_cadence_recommendation_triggers_and_skips() -> None:
    meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-01-08"),
        make_meeting("m3", date="2026-01-15"),
    ]
    sparse = [
        make_memory("d1", "decision", "D", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"),
    ]
    context = build_context(sparse, meetings)
    assert cadence_recommendation(context)

    busy = [
        make_memory(
            f"d{i}", "decision", f"D{i}", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"
        )
        for i in range(6)
    ]
    assert cadence_recommendation(build_context(busy, meetings)) == []

    few_meetings = build_context(sparse, [make_meeting("m1", date="2026-01-01")])
    assert cadence_recommendation(few_meetings) == []


def test_engine_recommendations_are_priority_sorted() -> None:
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
            "qa",
            meeting_id="m1",
            created_at="2026-01-01T09:02:00+00:00",
            metadata={"owner": "Alice"},
        ),
    ]
    store = load_store(meetings, memories)
    report = IntelligenceEngine().analyze(store)
    priorities = [r.priority for r in report.recommendations]
    assert priorities[0] is RecommendationPriority.URGENT
    store.close()


# -- report rendering ---------------------------------------------------------


def _report(*, with_entities: bool) -> InsightReport:
    health = OrganizationalHealth(
        reference_date="2026-01-01",
        decision=DecisionMetrics(total=2, active=1, stability=0.5),
        commitment=CommitmentMetrics(total=2, resolved=1, resolution_rate=0.5),
        risk=RiskMetrics(total=1, resolution_rate=0.0),
        meeting=MeetingMetrics(total_meetings=2),
        scores={"decision_stability": 0.5, "knowledge_reuse": 0.25},
        overall=0.4,
    )
    insights = (
        _insight(
            InsightType.LONG_RUNNING_DECISION, InsightCategory.DECISION, InsightSeverity.MEDIUM
        ),
        _insight(InsightType.AGING_COMMITMENT, InsightCategory.COMMITMENT, InsightSeverity.LOW),
        _insight(InsightType.RECURRING_RISK, InsightCategory.RISK, InsightSeverity.HIGH),
        _insight(InsightType.RISK_HOTSPOT, InsightCategory.PROJECT, InsightSeverity.HIGH),
        _insight(
            InsightType.OPEN_COMMITMENT_OVERLOAD, InsightCategory.PERSON, InsightSeverity.MEDIUM
        ),
    )
    recs = recommendations_from(list(insights))
    projects = (ProjectMetrics(project_id="project:atlas", name="Atlas", risk_count=3),)
    people = (PersonMetrics(name="Alice", open_commitments=3),)
    return InsightReport(
        reference_date="2026-01-01",
        health=health,
        insights=insights,
        recommendations=tuple(recs),
        projects=projects if with_entities else (),
        people=people if with_entities else (),
    )


def test_to_json_is_valid_and_complete() -> None:
    report = _report(with_entities=True)
    payload = json.loads(to_json(report))
    assert payload["health"]["overall"] == 0.4
    assert len(payload["insights"]) == 5


def test_to_markdown_has_all_sections() -> None:
    text = to_markdown(_report(with_entities=True))
    for heading in (
        "## Executive summary",
        "## Organizational health",
        "## Decision insights",
        "## Commitment insights",
        "## Risk insights",
        "## Recommendations",
        "## Appendix",
    ):
        assert heading in text
    assert "| Atlas |" in text
    assert "| Alice |" in text


def test_markdown_and_text_handle_empty_entities() -> None:
    md = to_markdown(_report(with_entities=False))
    assert "None" in md
    txt = to_text(_report(with_entities=False))
    assert "None" in txt


def test_render_report_dispatch_and_unknown() -> None:
    report = _report(with_entities=True)
    assert REPORT_FORMATS == ("json", "markdown", "text")
    assert render_report(report, "json").startswith("{")
    assert render_report(report, "markdown").startswith("#")
    assert "ORGANIZATIONAL" in render_report(report, "text")
    with pytest.raises(ValueError, match="Unknown report format"):
        render_report(report, "xml")


def test_text_report_lists_insights_and_recommendations() -> None:
    text = to_text(_report(with_entities=True))
    assert "DECISION INSIGHTS" in text
    assert "RECOMMENDATIONS" in text
    assert "Atlas" in text


def test_empty_report_sections_say_none() -> None:
    health = OrganizationalHealth(
        reference_date="",
        decision=DecisionMetrics(),
        commitment=CommitmentMetrics(),
        risk=RiskMetrics(),
        meeting=MeetingMetrics(),
    )
    report = InsightReport(reference_date="", health=health)
    md = to_markdown(report)
    assert md.count("- None") >= 4
    assert "n/a" in md
    text = to_text(report)
    assert "None" in text


def test_resolved_status_constant_used_in_report_helpers() -> None:
    # Sanity: report helpers operate purely on the report object.
    report = _report(with_entities=True)
    assert report.health.commitment.resolution_rate == 0.5
    assert MemoryStatus.RESOLVED.value == "resolved"
