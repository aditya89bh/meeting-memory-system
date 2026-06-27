"""Deterministic risk intelligence.

Surfaces recurring risks, long-unresolved risks, long-lived risk lineages, and
project risk hotspots / recurring blockers (using the graph), and computes the
aggregate :class:`RiskMetrics`.
"""

from __future__ import annotations

from ..storage import MemoryStatus, StoredMemory
from .analysis import (
    days_between,
    insight_id,
    memory_evidence,
    project_metrics,
    recurring_groups,
    scale_severity,
)
from .context import AnalysisContext
from .models import (
    Insight,
    InsightCategory,
    InsightEvidence,
    InsightType,
    RiskMetrics,
)
from .providers import InsightProvider, MetricProvider, ProviderMetadata
from .registry import register_insight, register_metric

_RESOLVED_STATUSES = (MemoryStatus.RESOLVED, MemoryStatus.ARCHIVED)
# Meetings a risk must reappear in to count as "recurring".
_RECUR_MIN = 2
# Days an active risk may persist before it is "unresolved".
_UNRESOLVED_DAYS = 30
# Days a recurring risk lineage spans before it is "long lived".
_LONG_LIVED_DAYS = 60
# Distinct risks on one project before it is a "hotspot".
_HOTSPOT_MIN = 3
# Recurring blocker edges on one project before it is flagged.
_BLOCKER_MIN = 2


def risk_metrics(context: AnalysisContext) -> RiskMetrics:
    """Compute aggregate risk statistics for ``context``."""
    risks = context.by_type("risk")
    total = len(risks)
    if total == 0:
        return RiskMetrics()

    resolved = sum(1 for r in risks if r.status in _RESOLVED_STATUSES)
    open_items = sum(1 for r in risks if r.status is MemoryStatus.ACTIVE)
    groups = recurring_groups(risks)
    max_recurrence = max(
        (len({m.meeting_id for m in items}) for items in groups.values()), default=0
    )

    hotspot = None
    rows = sorted(project_metrics(context), key=lambda p: (-p.risk_count, p.project_id))
    if rows and rows[0].risk_count > 0:
        hotspot = rows[0].name

    meetings = max(len(context.meetings), 1)
    return RiskMetrics(
        total=total,
        open=open_items,
        resolved=resolved,
        resolution_rate=round(resolved / total, 4),
        recurring=len(groups),
        max_recurrence=max_recurrence,
        density=round(total / meetings, 4),
        hotspot_project=hotspot,
    )


def risk_insights(context: AnalysisContext) -> list[Insight]:
    """Discover deterministic risk insights for ``context``."""
    risks = context.by_type("risk")
    if not risks:
        return []
    insights: list[Insight] = []
    insights.extend(_recurring_insights(risks, context))
    insights.extend(_unresolved_insights(risks, context))
    insights.extend(_hotspot_insights(context))
    return insights


def _recurring_insights(risks: list[StoredMemory], context: AnalysisContext) -> list[Insight]:
    insights: list[Insight] = []
    for items in recurring_groups(risks).values():
        meetings = len({item.meeting_id for item in items})
        if meetings < _RECUR_MIN:
            continue
        sample = items[0]
        dates = sorted(d for d in (context.memory_date(m) for m in items) if d)
        span = days_between(dates[0], dates[-1]) if len(dates) > 1 else 0
        unresolved = all(item.status is MemoryStatus.ACTIVE for item in items)
        insights.append(
            Insight(
                insight_id=insight_id("risk", "recurring", sample.content_hash),
                type=InsightType.RECURRING_RISK,
                category=InsightCategory.RISK,
                severity=scale_severity(meetings, _RECUR_MIN, 4, 6),
                title=f"Risk recurred in {meetings} meetings",
                detail=(
                    f"{_quote(sample.text)} has appeared in {meetings} meetings"
                    + (" and is still unresolved." if unresolved else ".")
                ),
                metric=float(meetings),
                subjects=(sample.content_hash,),
                evidence=(
                    memory_evidence(
                        items, f"Appeared in {meetings} meetings.", value=float(meetings)
                    ),
                ),
            )
        )
        if span >= _LONG_LIVED_DAYS:
            insights.append(
                Insight(
                    insight_id=insight_id("risk", "longlived", sample.content_hash),
                    type=InsightType.LONG_LIVED_RISK,
                    category=InsightCategory.RISK,
                    severity=scale_severity(span, _LONG_LIVED_DAYS, 120, 240),
                    title=f"Risk persisted for {span} days",
                    detail=f"{_quote(sample.text)} has been raised over a {span}-day span.",
                    metric=float(span),
                    subjects=(sample.content_hash,),
                    evidence=(memory_evidence(items, f"Spanning {span} days.", value=float(span)),),
                )
            )
    return insights


def _unresolved_insights(risks: list[StoredMemory], context: AnalysisContext) -> list[Insight]:
    insights: list[Insight] = []
    for risk in risks:
        if risk.status is not MemoryStatus.ACTIVE:
            continue
        meeting_date = context.memory_date(risk)
        if not meeting_date:
            continue
        age = days_between(meeting_date, context.reference_date)
        if age < _UNRESOLVED_DAYS:
            continue
        insights.append(
            Insight(
                insight_id=insight_id("risk", "unresolved", risk.memory_id),
                type=InsightType.UNRESOLVED_RISK,
                category=InsightCategory.RISK,
                severity=scale_severity(age, _UNRESOLVED_DAYS, 90, 180),
                title=f"Risk unresolved for {age} days",
                detail=f"{_quote(risk.text)} has remained open for {age} days.",
                metric=float(age),
                subjects=(risk.memory_id,),
                evidence=(memory_evidence([risk], f"Open for {age} days.", value=float(age)),),
            )
        )
    return insights


def _hotspot_insights(context: AnalysisContext) -> list[Insight]:
    if context.graph is None:
        return []
    insights: list[Insight] = []
    for row in project_metrics(context):
        if row.risk_count >= _HOTSPOT_MIN:
            insights.append(
                Insight(
                    insight_id=insight_id("risk", "hotspot", row.project_id),
                    type=InsightType.RISK_HOTSPOT,
                    category=InsightCategory.PROJECT,
                    severity=scale_severity(row.risk_count, _HOTSPOT_MIN, 5, 8),
                    title=f"{row.name} is a risk hotspot",
                    detail=(
                        f"{row.name} is linked to {row.risk_count} risks across the "
                        "analysed meetings."
                    ),
                    metric=float(row.risk_count),
                    subjects=(row.project_id,),
                    evidence=(_project_evidence(row.project_id, row.risk_count, "risks"),),
                )
            )
        if row.blocker_count >= _BLOCKER_MIN:
            insights.append(
                Insight(
                    insight_id=insight_id("project", "blocker", row.project_id),
                    type=InsightType.PROJECT_BLOCKER,
                    category=InsightCategory.PROJECT,
                    severity=scale_severity(row.blocker_count, _BLOCKER_MIN, 4, 6),
                    title=f"{row.name} has recurring blockers",
                    detail=(
                        f"{row.name} is blocked by {row.blocker_count} risks, indicating "
                        "a recurring bottleneck."
                    ),
                    metric=float(row.blocker_count),
                    subjects=(row.project_id,),
                    evidence=(_project_evidence(row.project_id, row.blocker_count, "blockers"),),
                )
            )
    return insights


def _project_evidence(project_id: str, count: int, label: str) -> InsightEvidence:
    """Graph-node-based evidence for a project metric."""
    return InsightEvidence(
        description=f"{count} {label} linked to {project_id}.",
        node_ids=(project_id,),
        value=float(count),
    )


def _quote(text: str, limit: int = 80) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) > limit:
        collapsed = collapsed[: limit - 1].rstrip() + "\u2026"
    return f"\u201c{collapsed}\u201d"


class RiskInsightProvider(InsightProvider):
    """Provider exposing :func:`risk_insights`."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="risk-insights",
            version="1.0",
            category=InsightCategory.RISK,
            description="Recurring, unresolved, long-lived risks and project hotspots.",
        )

    def analyze(self, context: AnalysisContext) -> list[Insight]:
        return risk_insights(context)


class RiskMetricProvider(MetricProvider):
    """Provider exposing :func:`risk_metrics`."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="risk-metrics",
            version="1.0",
            category=InsightCategory.RISK,
            description="Open/resolved counts, recurrence, density, and hotspot.",
        )

    def analyze(self, context: AnalysisContext) -> RiskMetrics:
        return risk_metrics(context)


register_insight(RiskInsightProvider())
register_metric(RiskMetricProvider())

__all__ = [
    "RiskInsightProvider",
    "RiskMetricProvider",
    "risk_insights",
    "risk_metrics",
]
