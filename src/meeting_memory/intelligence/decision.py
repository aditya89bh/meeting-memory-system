"""Deterministic decision intelligence.

Surfaces repeatedly superseded decisions, frequently revisited decisions,
long-running decisions, and overall decision instability, and computes the
aggregate :class:`DecisionMetrics` (density, velocity, ownership, stability).
"""

from __future__ import annotations

from ..storage import MemoryStatus, StoredMemory
from .analysis import (
    chain_span_days,
    insight_id,
    memory_evidence,
    recurring_groups,
    scale_severity,
    supersession_chains,
    top_counter,
)
from .context import AnalysisContext
from .models import (
    DecisionMetrics,
    Insight,
    InsightCategory,
    InsightSeverity,
    InsightType,
)
from .providers import InsightProvider, MetricProvider, ProviderMetadata
from .registry import register_insight, register_metric

# How many supersessions before a decision is "repeatedly" superseded.
_REPEATED_SUPERSEDE_MIN = 2
# How many meetings a decision must reappear in to count as "revisited".
_REVISIT_MIN = 2
# Days before a decision lineage is "long running".
_LONG_RUNNING_DAYS = 30
# Stability below which the decision base is flagged as unstable.
_UNSTABLE_STABILITY = 0.5
_UNSTABLE_MIN_DECISIONS = 4


def decision_metrics(context: AnalysisContext) -> DecisionMetrics:
    """Compute aggregate decision statistics for ``context``."""
    decisions = context.by_type("decision")
    total = len(decisions)
    if total == 0:
        return DecisionMetrics()

    active = sum(1 for d in decisions if d.status is MemoryStatus.ACTIVE)
    superseded = sum(1 for d in decisions if d.status is MemoryStatus.SUPERSEDED)
    revisited = sum(len(items) for items in recurring_groups(decisions).values())

    owners: dict[str, int] = {}
    for decision in decisions:
        if decision.speaker:
            owners[decision.speaker] = owners.get(decision.speaker, 0) + 1
    top_owner, _ = top_counter(owners)

    meetings = max(len(context.meetings), 1)
    weeks = max(context.span_days, 7) / 7.0
    return DecisionMetrics(
        total=total,
        active=active,
        superseded=superseded,
        revisited=revisited,
        stability=round(active / total, 4),
        density=round(total / meetings, 4),
        velocity_per_week=round(total / weeks, 4),
        distinct_owners=len(owners),
        top_owner=top_owner,
    )


def decision_insights(context: AnalysisContext) -> list[Insight]:
    """Discover deterministic decision insights for ``context``."""
    decisions = context.by_type("decision")
    if not decisions:
        return []
    index: dict[str, StoredMemory] = {m.memory_id: m for m in context.memories}
    insights: list[Insight] = []
    insights.extend(_superseded_insights(decisions, index, context))
    insights.extend(_revisited_insights(decisions, context))
    insights.extend(_unstable_insight(decisions))
    return insights


def _superseded_insights(
    decisions: list[StoredMemory],
    index: dict[str, StoredMemory],
    context: AnalysisContext,
) -> list[Insight]:
    insights: list[Insight] = []
    for chain in supersession_chains(decisions, index):
        supersessions = len(chain) - 1
        latest = chain[-1]
        span = chain_span_days(chain, context)
        if supersessions >= _REPEATED_SUPERSEDE_MIN:
            severity = scale_severity(supersessions, _REPEATED_SUPERSEDE_MIN, 3, 5)
            insights.append(
                Insight(
                    insight_id=insight_id("decision", "superseded", latest.memory_id),
                    type=InsightType.REPEATEDLY_SUPERSEDED_DECISION,
                    category=InsightCategory.DECISION,
                    severity=severity,
                    title=f"Decision changed {supersessions} times",
                    detail=(
                        f"{_quote(latest.text)} has been superseded {supersessions} "
                        "times, suggesting an unsettled decision."
                    ),
                    metric=float(supersessions),
                    subjects=(latest.memory_id,),
                    evidence=(
                        memory_evidence(
                            chain,
                            f"Supersession chain of {len(chain)} decisions.",
                            value=float(supersessions),
                        ),
                    ),
                )
            )
        if span >= _LONG_RUNNING_DAYS:
            insights.append(
                Insight(
                    insight_id=insight_id("decision", "longrunning", latest.memory_id),
                    type=InsightType.LONG_RUNNING_DECISION,
                    category=InsightCategory.DECISION,
                    severity=scale_severity(span, _LONG_RUNNING_DAYS, 90, 180),
                    title=f"Decision lineage spans {span} days",
                    detail=(
                        f"{_quote(latest.text)} has been reworked over {span} days "
                        "without settling."
                    ),
                    metric=float(span),
                    subjects=(latest.memory_id,),
                    evidence=(
                        memory_evidence(chain, f"Lineage spanning {span} days.", value=float(span)),
                    ),
                )
            )
    return insights


def _revisited_insights(decisions: list[StoredMemory], context: AnalysisContext) -> list[Insight]:
    insights: list[Insight] = []
    for items in recurring_groups(decisions).values():
        meetings = len({item.meeting_id for item in items})
        if meetings < _REVISIT_MIN:
            continue
        sample = items[0]
        insights.append(
            Insight(
                insight_id=insight_id("decision", "revisited", sample.content_hash),
                type=InsightType.REVISITED_DECISION,
                category=InsightCategory.DECISION,
                severity=scale_severity(meetings, _REVISIT_MIN, 4, 6),
                title=f"Decision revisited across {meetings} meetings",
                detail=(
                    f"{_quote(sample.text)} was discussed in {meetings} separate "
                    "meetings without a durable resolution."
                ),
                metric=float(meetings),
                subjects=(sample.content_hash,),
                evidence=(
                    memory_evidence(
                        items, f"Repeated in {meetings} meetings.", value=float(meetings)
                    ),
                ),
            )
        )
    return insights


def _unstable_insight(decisions: list[StoredMemory]) -> list[Insight]:
    total = len(decisions)
    if total < _UNSTABLE_MIN_DECISIONS:
        return []
    active = sum(1 for d in decisions if d.status is MemoryStatus.ACTIVE)
    stability = active / total
    if stability >= _UNSTABLE_STABILITY:
        return []
    return [
        Insight(
            insight_id=insight_id("decision", "unstable"),
            type=InsightType.UNSTABLE_DECISIONS,
            category=InsightCategory.DECISION,
            severity=InsightSeverity.MEDIUM,
            title=f"Decision stability is low ({stability:.0%})",
            detail=(
                f"Only {active} of {total} decisions remain active; the rest were "
                "superseded or archived."
            ),
            metric=round(stability, 4),
            evidence=(
                memory_evidence(
                    decisions,
                    f"{active}/{total} decisions still active.",
                    value=round(stability, 4),
                ),
            ),
        )
    ]


def _quote(text: str, limit: int = 80) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) > limit:
        collapsed = collapsed[: limit - 1].rstrip() + "\u2026"
    return f"\u201c{collapsed}\u201d"


class DecisionInsightProvider(InsightProvider):
    """Provider exposing :func:`decision_insights`."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="decision-insights",
            version="1.0",
            category=InsightCategory.DECISION,
            description="Repeated supersessions, revisits, and decision instability.",
        )

    def analyze(self, context: AnalysisContext) -> list[Insight]:
        return decision_insights(context)


class DecisionMetricProvider(MetricProvider):
    """Provider exposing :func:`decision_metrics`."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="decision-metrics",
            version="1.0",
            category=InsightCategory.DECISION,
            description="Aggregate decision density, velocity, ownership, and stability.",
        )

    def analyze(self, context: AnalysisContext) -> DecisionMetrics:
        return decision_metrics(context)


register_insight(DecisionInsightProvider())
register_metric(DecisionMetricProvider())

__all__ = [
    "DecisionInsightProvider",
    "DecisionMetricProvider",
    "decision_insights",
    "decision_metrics",
]
