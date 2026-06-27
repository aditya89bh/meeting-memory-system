"""Edge-case tests closing remaining branches across the intelligence layer."""

from __future__ import annotations

from intelligence_helpers import load_store, make_meeting, make_memory
from meeting_memory.graph import SQLiteGraphStore
from meeting_memory.intelligence import InsightType, IntelligenceEngine
from meeting_memory.intelligence.analysis import (
    chain_span_days,
    person_metrics,
    project_metrics,
    supersession_chains,
)
from meeting_memory.intelligence.commitment import commitment_insights, commitment_metrics
from meeting_memory.intelligence.context import AnalysisContext, AnalysisFilters, build_context
from meeting_memory.intelligence.decision import decision_insights, decision_metrics
from meeting_memory.intelligence.models import InsightCategory
from meeting_memory.intelligence.providers import (
    InsightProvider,
    MetricProvider,
    ProviderMetadata,
    RecommendationProvider,
)
from meeting_memory.intelligence.registry import ProviderSet
from meeting_memory.intelligence.risk import risk_insights
from meeting_memory.storage import MemoryStatus


def _context(meetings, memories, **kwargs):
    return build_context(memories, meetings, **kwargs)


def test_analysis_filters_to_dict() -> None:
    filters = AnalysisFilters(project="Atlas", person="Alice", meetings=frozenset({"m1"}))
    payload = filters.to_dict()
    assert payload["project"] == "Atlas"
    assert payload["meetings"] == ["m1"]


def test_span_days_with_unparsable_dates() -> None:
    meetings = [make_meeting("m1", date="bad"), make_meeting("m2", date="worse")]
    assert _context(meetings, []).span_days == 0


def test_meeting_filter_excludes_other_meeting_memories() -> None:
    meetings = [make_meeting("m1", date="2026-01-01"), make_meeting("m2", date="2026-02-01")]
    memories = [
        make_memory("a", "fact", "x", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"),
        make_memory("b", "fact", "y", meeting_id="m2", created_at="2026-02-01T09:00:00+00:00"),
    ]
    context = _context(meetings, memories, filters=AnalysisFilters(meetings=frozenset({"m1"})))
    assert {m.memory_id for m in context.memories} == {"a"}


def test_supersession_chain_with_dangling_pointer() -> None:
    dangling = make_memory(
        "d0",
        "decision",
        "A",
        meeting_id="m1",
        created_at="2026-01-01T09:00:00+00:00",
        superseded_by="ghost",
    )
    assert supersession_chains([dangling], {"d0": dangling}) == []


def test_chain_span_days_single_member() -> None:
    memory = make_memory(
        "d", "decision", "A", meeting_id="m1", created_at="2026-01-01T09:00:00+00:00"
    )
    context = _context([make_meeting("m1", date="2026-01-01")], [memory])
    assert chain_span_days([memory], context) == 0


def test_person_metrics_owner_and_status_branches() -> None:
    meetings = [make_meeting("m1", date="2026-01-01", participants=())]
    memories = [
        make_memory(
            "c1",
            "commitment",
            "no owner",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            speaker=None,
        ),
        make_memory(
            "c2",
            "commitment",
            "done",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            metadata={"owner": "Bob"},
            status=MemoryStatus.RESOLVED,
        ),
    ]
    metrics = {p.name: p for p in person_metrics(_context(meetings, memories))}
    # c1 has no owner/speaker -> contributes to nobody.
    assert "Bob" in metrics
    assert metrics["Bob"].total_commitments == 1
    assert metrics["Bob"].open_commitments == 0


def test_decision_metrics_skips_speakerless() -> None:
    meetings = [make_meeting("m1", date="2026-01-01")]
    memories = [
        make_memory(
            "d1",
            "decision",
            "A",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            speaker=None,
        ),
    ]
    assert decision_metrics(_context(meetings, memories)).distinct_owners == 0


def test_decision_two_chain_long_running_and_short_repeated() -> None:
    # Two-decision chain spanning >30 days: long running but not repeated.
    meetings = [make_meeting("m1", date="2026-01-01"), make_meeting("m2", date="2026-03-01")]
    memories = [
        make_memory(
            "d1",
            "decision",
            "A",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            status=MemoryStatus.SUPERSEDED,
            superseded_by="d2",
        ),
        make_memory("d2", "decision", "B", meeting_id="m2", created_at="2026-03-01T09:00:00+00:00"),
    ]
    types = {i.type for i in decision_insights(_context(meetings, memories))}
    assert InsightType.LONG_RUNNING_DECISION in types
    assert InsightType.REPEATEDLY_SUPERSEDED_DECISION not in types

    # Three-decision chain within a single month: repeated but not long running.
    short_meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-01-05"),
        make_meeting("m3", date="2026-01-10"),
    ]
    short = [
        make_memory(
            "s1",
            "decision",
            "A",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            status=MemoryStatus.SUPERSEDED,
            superseded_by="s2",
        ),
        make_memory(
            "s2",
            "decision",
            "B",
            meeting_id="m2",
            created_at="2026-01-05T09:00:00+00:00",
            status=MemoryStatus.SUPERSEDED,
            superseded_by="s3",
        ),
        make_memory("s3", "decision", "C", meeting_id="m3", created_at="2026-01-10T09:00:00+00:00"),
    ]
    short_types = {i.type for i in decision_insights(_context(short_meetings, short))}
    assert InsightType.REPEATEDLY_SUPERSEDED_DECISION in short_types
    assert InsightType.LONG_RUNNING_DECISION not in short_types


def test_risk_recurring_resolved_undated_and_unresolved() -> None:
    long_text = "There is a serious risk that the migration will overrun the budget badly " * 2
    meetings = [
        make_meeting("m1", date="2026-01-01"),
        make_meeting("m2", date="2026-02-01"),
        make_meeting("m3", date="2026-04-01"),
        make_meeting("m4", date=None),
    ]
    memories = [
        make_memory(
            "r1",
            "risk",
            long_text,
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            content_hash="dup",
            status=MemoryStatus.RESOLVED,
        ),
        make_memory(
            "r2",
            "risk",
            long_text,
            meeting_id="m2",
            created_at="2026-02-01T09:00:00+00:00",
            content_hash="dup",
        ),
        make_memory(
            "r4",
            "risk",
            "Undated risk",
            meeting_id="m4",
            created_at="2026-03-01T09:00:00+00:00",
            content_hash="solo",
        ),
    ]
    insights = risk_insights(_context(meetings, memories))
    recurring = next(i for i in insights if i.type is InsightType.RECURRING_RISK)
    # Not all active -> sentence ends with a period, not "still unresolved".
    assert recurring.detail.rstrip().endswith("meetings.")
    # Long sample text is truncated with an ellipsis.
    assert "\u2026" in recurring.detail
    # r2 is active and older than the unresolved threshold.
    assert any(i.type is InsightType.UNRESOLVED_RISK for i in insights)


def test_project_metrics_counts_all_source_types() -> None:
    meetings = [make_meeting("m1", date="2026-01-01", title="Project Atlas Kickoff")]
    memories = [
        make_memory(
            "r1",
            "risk",
            "Project Atlas may slip",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
        ),
        make_memory(
            "d1",
            "decision",
            "Adopt staging for Project Atlas",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
        ),
        make_memory(
            "c1",
            "commitment",
            "Finish the Project Atlas migration",
            meeting_id="m1",
            created_at="2026-01-01T09:02:00+00:00",
            metadata={"owner": "Bob"},
        ),
    ]
    store = load_store(meetings, memories)
    graph = SQLiteGraphStore(":memory:")
    IntelligenceEngine().analyze(store, graph)
    rows = {
        r.name: r
        for r in project_metrics(build_context(store.list(), store.list_meetings(), graph=graph))
    }
    atlas = rows["Atlas"]
    assert atlas.risk_count >= 1
    assert atlas.decision_count >= 1
    assert atlas.meeting_count >= 1
    graph.close()
    store.close()


def test_commitment_metrics_open_without_meeting_date() -> None:
    meetings = [make_meeting("m1", date=None)]
    memories = [
        make_memory(
            "c1",
            "commitment",
            "x",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            metadata={"owner": "Bob"},
        ),
        make_memory(
            "c2",
            "commitment",
            "ownerless",
            meeting_id="m1",
            created_at="2026-01-01T09:01:00+00:00",
            speaker=None,
        ),
    ]
    context = _context(meetings, memories)
    metrics = commitment_metrics(context)
    assert metrics.avg_open_age_days == 0.0
    # Aging loop encounters commitments whose meeting has no date.
    assert all(i.type is not InsightType.AGING_COMMITMENT for i in commitment_insights(context))


def test_commitment_overdue_unassigned_and_quoted() -> None:
    long_text = "We absolutely must finalize the detailed rollout and migration plan soon " * 2
    meetings = [make_meeting("m1", date="2026-01-01"), make_meeting("m2", date="2026-06-01")]
    memories = [
        make_memory(
            "c1",
            "commitment",
            long_text,
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            speaker=None,
            metadata={"due": "2026-01-15"},
        ),
    ]
    overdue = next(
        i
        for i in commitment_insights(_context(meetings, memories))
        if i.type is InsightType.OVERDUE_COMMITMENT
    )
    assert "unassigned" in overdue.detail
    assert "\u2026" in overdue.detail


class _NoSupportInsight(InsightProvider):
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata("no-insight", "1.0", InsightCategory.DECISION, "x")

    def supports(self, context: AnalysisContext) -> bool:
        return False

    def analyze(self, context: AnalysisContext) -> list:  # pragma: no cover - never run
        raise AssertionError("should not run")


class _NoSupportMetric(MetricProvider):
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata("no-metric", "1.0", InsightCategory.DECISION, "x")

    def supports(self, context: AnalysisContext) -> bool:
        return False

    def analyze(self, context: AnalysisContext) -> object:  # pragma: no cover - never run
        raise AssertionError("should not run")


class _NoSupportRecommendation(RecommendationProvider):
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata("no-rec", "1.0", InsightCategory.DECISION, "x")

    def supports(self, context: AnalysisContext) -> bool:
        return False

    def analyze(self, context: AnalysisContext, insights: list) -> list:  # pragma: no cover
        raise AssertionError("should not run")


def test_engine_skips_unsupported_providers() -> None:
    providers = ProviderSet(
        insight=(_NoSupportInsight(),),
        metric=(_NoSupportMetric(),),
        recommendation=(_NoSupportRecommendation(),),
    )
    store = load_store([make_meeting("m1", date="2026-01-01")], [])
    report = IntelligenceEngine(providers).analyze(store)
    assert report.insights == ()
    assert report.recommendations == ()
    assert report.health.decision.total == 0
    store.close()
