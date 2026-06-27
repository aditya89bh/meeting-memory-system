"""The intelligence engine: discover providers, run them, assemble a report.

The engine is the orchestrator of Phase 6. It builds a deterministic
:class:`AnalysisContext` from the storage and graph layers, discovers every
registered provider, executes the ones that ``supports()`` the context, and
assembles an immutable :class:`InsightReport`. Health scores are composed from
the discovered metric providers plus context-level signals (knowledge reuse,
collaboration, resolution time).
"""

from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from ..graph import GraphStore, build_graph
from ..storage import MemoryStatus, MemoryStore
from .context import AnalysisContext, AnalysisFilters, build_context
from .models import (
    SEVERITY_ORDER,
    CommitmentMetrics,
    DecisionMetrics,
    Insight,
    InsightReport,
    MeetingMetrics,
    OrganizationalHealth,
    PersonMetrics,
    ProjectMetrics,
    Recommendation,
    RiskMetrics,
)
from .registry import ProviderSet, default_providers

# Productivity (decisions + commitments per meeting) treated as a healthy ceiling.
_PRODUCTIVITY_TARGET = 3.0
# Score keys that contribute to the overall health number.
_OVERALL_KEYS = (
    "decision_stability",
    "commitment_completion",
    "risk_resolution",
    "meeting_productivity",
    "knowledge_reuse",
    "cross_team_collaboration",
)


class IntelligenceEngine:
    """Discover and execute intelligence providers against stored memory."""

    def __init__(self, providers: ProviderSet | None = None) -> None:
        self._providers = providers if providers is not None else default_providers()

    @property
    def providers(self) -> ProviderSet:
        """The provider set this engine runs."""
        return self._providers

    # -- top-level orchestration ----------------------------------------------

    def analyze(
        self,
        memory_store: MemoryStore,
        graph_store: GraphStore | None = None,
        *,
        filters: AnalysisFilters | None = None,
        reference_date: str | None = None,
    ) -> InsightReport:
        """Build a context from the stores and produce a full report."""
        if graph_store is not None:
            build_graph(memory_store, graph_store)
        context = build_context(
            memory_store.list(),
            memory_store.list_meetings(),
            filters=filters,
            graph=graph_store,
            reference_date=reference_date,
        )
        return self.build_report(context)

    def build_report(self, context: AnalysisContext) -> InsightReport:
        """Assemble the full :class:`InsightReport` for ``context``."""
        insights = self.run_insights(context)
        health = self.run_health(context)
        recommendations = self.run_recommendations(context, insights)
        projects, people = self.run_entity_metrics(context)
        return InsightReport(
            reference_date=context.reference_date,
            health=health,
            insights=tuple(insights),
            recommendations=tuple(recommendations),
            projects=tuple(projects),
            people=tuple(people),
        )

    # -- discovery-driven steps -----------------------------------------------

    def run_insights(self, context: AnalysisContext) -> list[Insight]:
        """Run every supported insight provider and return sorted insights."""
        collected: list[Insight] = []
        for provider in self._providers.insight:
            if provider.supports(context):
                collected.extend(provider.analyze(context))
        collected.sort(
            key=lambda insight: (
                -SEVERITY_ORDER[insight.severity],
                insight.category.value,
                insight.type.value,
                insight.insight_id,
            )
        )
        return collected

    def run_metrics(self, context: AnalysisContext) -> dict[str, object]:
        """Run every supported metric provider, keyed by provider name."""
        results: dict[str, object] = {}
        for provider in self._providers.metric:
            if provider.supports(context):
                results[provider.metadata().name] = provider.analyze(context)
        return results

    def run_recommendations(
        self, context: AnalysisContext, insights: list[Insight]
    ) -> list[Recommendation]:
        """Run every supported recommendation provider and sort the output."""
        from .models import PRIORITY_ORDER

        collected: list[Recommendation] = []
        for provider in self._providers.recommendation:
            if provider.supports(context):
                collected.extend(provider.analyze(context, insights))
        collected.sort(
            key=lambda rec: (
                -PRIORITY_ORDER[rec.priority],
                -SEVERITY_ORDER[rec.severity],
                rec.category.value,
                rec.recommendation_id,
            )
        )
        return collected

    def run_entity_metrics(
        self, context: AnalysisContext
    ) -> tuple[list[ProjectMetrics], list[PersonMetrics]]:
        """Compute per-project and per-person metrics from context and graph."""
        from .analysis import person_metrics, project_metrics

        return project_metrics(context), person_metrics(context)

    def run_health(self, context: AnalysisContext) -> OrganizationalHealth:
        """Compose the organizational-health snapshot from metric providers."""
        results = self.run_metrics(context)
        decision = _first(results, DecisionMetrics) or DecisionMetrics()
        commitment = _first(results, CommitmentMetrics) or CommitmentMetrics()
        risk = _first(results, RiskMetrics) or RiskMetrics()
        meeting = _first(results, MeetingMetrics) or MeetingMetrics()
        scores = _compose_scores(context, decision, commitment, risk, meeting)
        overall = round(
            sum(scores[key] for key in _OVERALL_KEYS) / len(_OVERALL_KEYS),
            4,
        )
        return OrganizationalHealth(
            reference_date=context.reference_date,
            decision=decision,
            commitment=commitment,
            risk=risk,
            meeting=meeting,
            scores=scores,
            overall=overall,
        )

    def render(self, report: InsightReport, fmt: str) -> str:
        """Render ``report`` using the report provider for ``fmt``."""
        for provider in self._providers.report:
            if provider.fmt() == fmt:
                return provider.analyze(report)
        available = ", ".join(sorted(provider.fmt() for provider in self._providers.report))
        raise ValueError(f"Unknown report format {fmt!r}. Available: {available or 'none'}")


_M = TypeVar("_M")


def _first(results: dict[str, object], kind: type[_M]) -> _M | None:
    for value in results.values():
        if isinstance(value, kind):
            return value
    return None


def _compose_scores(
    context: AnalysisContext,
    decision: DecisionMetrics,
    commitment: CommitmentMetrics,
    risk: RiskMetrics,
    meeting: MeetingMetrics,
) -> dict[str, float]:
    reuse, repeated = _reuse_scores(context)
    return {
        "decision_stability": round(decision.stability, 4),
        "commitment_completion": round(commitment.resolution_rate, 4),
        "risk_resolution": round(risk.resolution_rate, 4),
        "meeting_productivity": round(min(1.0, meeting.productivity / _PRODUCTIVITY_TARGET), 4),
        "knowledge_reuse": reuse,
        "repeated_discussion_rate": repeated,
        "cross_team_collaboration": _collaboration_score(context),
        "risk_density": round(risk.density, 4),
        "avg_resolution_days": _avg_resolution_days(context),
    }


def _reuse_scores(context: AnalysisContext) -> tuple[float, float]:
    """Return (knowledge_reuse, repeated_discussion_rate) from content recurrence."""
    meetings_by_hash: dict[str, set[str]] = {}
    for memory in context.memories:
        meetings_by_hash.setdefault(memory.content_hash, set()).add(memory.meeting_id)
    total = len(context.memories)
    if total == 0:
        return 0.0, 0.0
    reused_memories = sum(
        1 for memory in context.memories if len(meetings_by_hash[memory.content_hash]) > 1
    )
    groups = len(meetings_by_hash)
    repeated_groups = sum(1 for ids in meetings_by_hash.values() if len(ids) > 1)
    reuse = round(reused_memories / total, 4)
    repeated = round(repeated_groups / groups, 4) if groups else 0.0
    return reuse, repeated


def _collaboration_score(context: AnalysisContext) -> float:
    """Fraction of participants who share a meeting with at least one other."""
    counts: dict[str, int] = {}
    collaborators: set[str] = set()
    for meeting in context.meetings:
        people = sorted(set(meeting.participants))
        if len(people) > 1:
            collaborators.update(people)
        for person in people:
            counts[person] = counts.get(person, 0) + 1
    if not counts:
        return 0.0
    return round(len(collaborators) / len(counts), 4)


def _avg_resolution_days(context: AnalysisContext) -> float:
    """Average days from creation to resolution for resolved memories."""
    spans: list[float] = []
    for memory in context.memories:
        if memory.status in (MemoryStatus.RESOLVED, MemoryStatus.ARCHIVED):
            days = _timestamp_days(memory.created_at, memory.updated_at)
            if days is not None:
                spans.append(days)
    if not spans:
        return 0.0
    return round(sum(spans) / len(spans), 2)


def _timestamp_days(start: str, end: str) -> float | None:
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    except ValueError:
        return None
    return delta.total_seconds() / 86400.0


__all__ = ["IntelligenceEngine"]
