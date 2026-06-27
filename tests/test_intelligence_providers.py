"""Tests for the intelligence models, context, providers, registry, and engine."""

from __future__ import annotations

import pytest

from intelligence_helpers import load_store, make_meeting, make_memory
from meeting_memory.graph import SQLiteGraphStore
from meeting_memory.intelligence import (
    PRIORITY_ORDER,
    SEVERITY_ORDER,
    AnalysisFilters,
    Insight,
    InsightCategory,
    InsightEvidence,
    InsightReport,
    InsightSeverity,
    InsightType,
    IntelligenceEngine,
    OrganizationalHealth,
    ProviderSet,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    build_context,
    default_providers,
    owner_of,
)
from meeting_memory.intelligence.decision import DecisionInsightProvider, DecisionMetricProvider
from meeting_memory.intelligence.models import (
    CommitmentMetrics,
    DecisionMetrics,
    MeetingMetrics,
    PersonMetrics,
    ProjectMetrics,
    RiskMetrics,
)
from meeting_memory.intelligence.registry import (
    _replace,
    register_insight,
)
from meeting_memory.storage import MemoryStatus

# -- models -------------------------------------------------------------------


def test_enum_str_and_orderings() -> None:
    assert str(InsightSeverity.HIGH) == "high"
    assert str(InsightCategory.RISK) == "risk"
    assert str(InsightType.RECURRING_RISK) == "recurring_risk"
    assert str(RecommendationPriority.URGENT) == "urgent"
    assert str(RecommendationCategory.DECISION) == "decision"
    assert SEVERITY_ORDER[InsightSeverity.CRITICAL] > SEVERITY_ORDER[InsightSeverity.INFO]
    assert (
        PRIORITY_ORDER[RecommendationPriority.URGENT] > PRIORITY_ORDER[RecommendationPriority.LOW]
    )


def test_model_to_dict_roundtrips() -> None:
    evidence = InsightEvidence(
        description="d", memory_ids=("m1",), meeting_ids=("g1",), node_ids=("n1",), value=1.0
    )
    insight = Insight(
        insight_id="i1",
        type=InsightType.UNRESOLVED_RISK,
        category=InsightCategory.RISK,
        severity=InsightSeverity.HIGH,
        title="t",
        detail="detail",
        metric=2.0,
        subjects=("s",),
        evidence=(evidence,),
    )
    payload = insight.to_dict()
    assert payload["type"] == "unresolved_risk"
    assert payload["evidence"][0]["memory_ids"] == ["m1"]

    rec = Recommendation(
        recommendation_id="r1",
        priority=RecommendationPriority.HIGH,
        category=RecommendationCategory.RISK,
        severity=InsightSeverity.HIGH,
        title="t",
        detail="d",
        related_memory_ids=("m1",),
        evidence=(evidence,),
    )
    assert rec.to_dict()["priority"] == "high"

    for metric in (
        DecisionMetrics(),
        CommitmentMetrics(),
        RiskMetrics(),
        MeetingMetrics(),
        ProjectMetrics(project_id="project:atlas", name="Atlas"),
        PersonMetrics(name="Alice"),
    ):
        assert isinstance(metric.to_dict(), dict)


def test_organizational_health_and_report_to_dict() -> None:
    health = OrganizationalHealth(
        reference_date="2026-01-01",
        decision=DecisionMetrics(total=1),
        commitment=CommitmentMetrics(),
        risk=RiskMetrics(),
        meeting=MeetingMetrics(),
        scores={"a": 1.0},
        overall=0.5,
    )
    insight = Insight(
        insight_id="i1",
        type=InsightType.UNRESOLVED_RISK,
        category=InsightCategory.RISK,
        severity=InsightSeverity.HIGH,
        title="t",
        detail="d",
    )
    report = InsightReport(reference_date="2026-01-01", health=health, insights=(insight,))
    assert report.insights_by_category(InsightCategory.RISK) == [insight]
    assert report.insights_by_category(InsightCategory.DECISION) == []
    payload = report.to_dict()
    assert payload["health"]["overall"] == 0.5
    assert payload["insights"][0]["insight_id"] == "i1"


# -- context ------------------------------------------------------------------


def _dataset() -> tuple[list, list]:
    meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-02-01"),
    ]
    memories = [
        make_memory(
            "d1",
            "decision",
            "Pick a database",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
        ),
        make_memory(
            "c1",
            "commitment",
            "Ship docs",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            metadata={"owner": "Bob"},
        ),
        make_memory(
            "x1",
            "fact",
            "Deleted fact",
            meeting_id="m2",
            created_at="2026-02-01T09:00:00+00:00",
            status=MemoryStatus.DELETED,
        ),
    ]
    return meetings, memories


def test_owner_of_prefers_owner_then_speaker() -> None:
    _, memories = _dataset()
    commitment = memories[1]
    assert owner_of(commitment) == "Bob"
    assert owner_of(memories[0]) == "Alice"


def test_build_context_filters_and_reference_date() -> None:
    meetings, memories = _dataset()
    context = build_context(memories, meetings)
    assert context.reference_date == "2026-02-01"
    # DELETED memory excluded.
    assert all(m.memory_id != "x1" for m in context.memories)
    assert context.span_days == 31
    assert context.meeting("m1") is not None
    assert context.meeting("missing") is None
    assert context.meeting_date("m1") == "2026-01-01"
    assert context.meeting_date("missing") == ""
    assert context.memory_date(memories[0]) == "2026-01-01"


def test_build_context_explicit_filters() -> None:
    meetings, memories = _dataset()
    by_meeting = build_context(
        memories, meetings, filters=AnalysisFilters(meetings=frozenset({"m1"}))
    )
    assert {m.meeting_id for m in by_meeting.meetings} == {"m1"}

    by_person = build_context(memories, meetings, filters=AnalysisFilters(person="Bob"))
    assert {m.memory_id for m in by_person.memories} == {"c1"}

    by_type = build_context(
        memories, meetings, filters=AnalysisFilters(memory_types=frozenset({"decision"}))
    )
    assert {m.memory_id for m in by_type.memories} == {"d1"}

    override = build_context(memories, meetings, reference_date="2026-12-31")
    assert override.reference_date == "2026-12-31"


def test_build_context_empty_has_blank_reference() -> None:
    context = build_context([], [])
    assert context.reference_date == ""
    assert context.span_days == 0


def test_build_context_project_filter_uses_graph() -> None:
    meetings = [make_meeting("m1", date="2026-01-01", title="Project Atlas")]
    memories = [
        make_memory(
            "r1",
            "risk",
            "Project Atlas may slip",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
        ),
        make_memory(
            "f1",
            "fact",
            "Unrelated fact about coffee",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
        ),
    ]
    store = load_store(meetings, memories)
    graph = SQLiteGraphStore(":memory:")
    IntelligenceEngine().analyze(store, graph)  # builds graph

    context = build_context(
        store.list(), store.list_meetings(), filters=AnalysisFilters(project="Atlas"), graph=graph
    )
    assert {m.memory_id for m in context.memories} == {"r1"}

    missing = build_context(
        store.list(),
        store.list_meetings(),
        filters=AnalysisFilters(project="Nonexistent"),
        graph=graph,
    )
    assert missing.memories == ()
    graph.close()
    store.close()


# -- providers and registry ---------------------------------------------------


def test_provider_metadata_and_supports() -> None:
    provider = DecisionInsightProvider()
    meta = provider.metadata()
    assert meta.to_dict()["name"] == "decision-insights"
    meetings, memories = _dataset()
    context = build_context(memories, meetings)
    assert provider.supports(context) is True


def test_registry_replace_is_idempotent_by_name() -> None:
    provider = DecisionInsightProvider()
    before = len(default_providers().insight)
    register_insight(DecisionInsightProvider())  # same name replaces, no growth
    after = len(default_providers().insight)
    assert before == after

    registry: list = []
    _replace(registry, provider)
    _replace(registry, DecisionInsightProvider())
    assert len(registry) == 1


def test_default_providers_sorted_and_set_defaults() -> None:
    providers = default_providers()
    names = [p.metadata().name for p in providers.insight]
    assert names == sorted(names)
    assert isinstance(providers, ProviderSet)
    assert ProviderSet().report == ()


# -- engine -------------------------------------------------------------------


def test_engine_uses_custom_provider_set() -> None:
    custom = ProviderSet(
        insight=(DecisionInsightProvider(),),
        metric=(DecisionMetricProvider(),),
    )
    engine = IntelligenceEngine(custom)
    assert engine.providers is custom


def test_engine_render_unknown_format_raises() -> None:
    meetings, memories = _dataset()
    store = load_store(meetings, memories)
    engine = IntelligenceEngine()
    report = engine.analyze(store)
    with pytest.raises(ValueError, match="Unknown report format"):
        engine.render(report, "pdf")
    store.close()


def test_engine_analyze_without_graph_runs() -> None:
    meetings, memories = _dataset()
    store = load_store(meetings, memories)
    report = IntelligenceEngine().analyze(store)
    assert report.projects == ()
    assert report.health.meeting.total_meetings == 2
    assert 0.0 <= report.health.overall <= 1.0
    store.close()
