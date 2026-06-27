"""Deterministic commitment intelligence.

Surfaces commitment overload, overdue and aging commitments, and low resolution
rates, and computes aggregate :class:`CommitmentMetrics` (open/resolved counts,
resolution rate, workload, average open age).
"""

from __future__ import annotations

from datetime import date

from ..storage import MemoryStatus, StoredMemory
from .analysis import (
    days_between,
    insight_id,
    memory_evidence,
    scale_severity,
    top_counter,
)
from .context import AnalysisContext, owner_of
from .models import (
    CommitmentMetrics,
    Insight,
    InsightCategory,
    InsightSeverity,
    InsightType,
)
from .providers import InsightProvider, MetricProvider, ProviderMetadata
from .registry import register_insight, register_metric

# Open commitments owned by one person before it is "overload".
_OVERLOAD_MIN = 3
# Days an open commitment may age before it is flagged.
_AGING_DAYS = 30
# Resolution rate below which the commitment base is flagged.
_LOW_RESOLUTION = 0.4
_LOW_RESOLUTION_MIN = 4


def _is_overdue(memory: StoredMemory, reference_date: str) -> int:
    """Return whole days a commitment is overdue (0 if not overdue/undated)."""
    due = memory.metadata.get("due")
    if not due or memory.status is not MemoryStatus.ACTIVE or not reference_date:
        return 0
    try:
        date.fromisoformat(due)
    except ValueError:
        return 0
    overdue = days_between(due, reference_date)
    return overdue if overdue > 0 else 0


def commitment_metrics(context: AnalysisContext) -> CommitmentMetrics:
    """Compute aggregate commitment statistics for ``context``."""
    commitments = context.by_type("commitment")
    total = len(commitments)
    if total == 0:
        return CommitmentMetrics()

    resolved = sum(1 for c in commitments if c.status is MemoryStatus.RESOLVED)
    open_items = [c for c in commitments if c.status is MemoryStatus.ACTIVE]
    overdue = sum(1 for c in open_items if _is_overdue(c, context.reference_date) > 0)

    owners: dict[str, int] = {}
    for commitment in open_items:
        owner = owner_of(commitment)
        if owner:
            owners[owner] = owners.get(owner, 0) + 1
    top_owner, top_owner_open = top_counter(owners)

    ages = [
        days_between(date_str, context.reference_date)
        for commitment in open_items
        if (date_str := context.memory_date(commitment))
    ]
    avg_age = round(sum(ages) / len(ages), 2) if ages else 0.0

    return CommitmentMetrics(
        total=total,
        open=len(open_items),
        resolved=resolved,
        overdue=overdue,
        resolution_rate=round(resolved / total, 4),
        avg_open_age_days=avg_age,
        top_owner=top_owner,
        top_owner_open=top_owner_open,
    )


def commitment_insights(context: AnalysisContext) -> list[Insight]:
    """Discover deterministic commitment insights for ``context``."""
    commitments = context.by_type("commitment")
    if not commitments:
        return []
    open_items = [c for c in commitments if c.status is MemoryStatus.ACTIVE]
    insights: list[Insight] = []
    insights.extend(_overload_insights(open_items))
    insights.extend(_overdue_insights(open_items, context))
    insights.extend(_aging_insights(open_items, context))
    insights.extend(_resolution_insight(commitments))
    return insights


def _overload_insights(open_items: list[StoredMemory]) -> list[Insight]:
    by_owner: dict[str, list[StoredMemory]] = {}
    for commitment in open_items:
        owner = owner_of(commitment)
        if owner:
            by_owner.setdefault(owner, []).append(commitment)
    insights: list[Insight] = []
    for owner in sorted(by_owner):
        items = by_owner[owner]
        count = len(items)
        if count < _OVERLOAD_MIN:
            continue
        insights.append(
            Insight(
                insight_id=insight_id("commitment", "overload", owner),
                type=InsightType.OPEN_COMMITMENT_OVERLOAD,
                category=InsightCategory.PERSON,
                severity=scale_severity(count, _OVERLOAD_MIN, 5, 8),
                title=f"{owner} owns {count} open commitments",
                detail=(
                    f"{owner} is responsible for {count} unresolved commitments, "
                    "indicating a possible workload bottleneck."
                ),
                metric=float(count),
                subjects=(owner,),
                evidence=(
                    memory_evidence(
                        items, f"{count} open commitments owned by {owner}.", value=float(count)
                    ),
                ),
            )
        )
    return insights


def _overdue_insights(open_items: list[StoredMemory], context: AnalysisContext) -> list[Insight]:
    insights: list[Insight] = []
    for commitment in open_items:
        overdue = _is_overdue(commitment, context.reference_date)
        if overdue <= 0:
            continue
        owner = owner_of(commitment) or "unassigned"
        insights.append(
            Insight(
                insight_id=insight_id("commitment", "overdue", commitment.memory_id),
                type=InsightType.OVERDUE_COMMITMENT,
                category=InsightCategory.COMMITMENT,
                severity=scale_severity(overdue, 1, 14, 45),
                title=f"Commitment overdue by {overdue} days",
                detail=(
                    f"{_quote(commitment.text)} (owner: {owner}) was due "
                    f"{commitment.metadata.get('due')} and is {overdue} days overdue."
                ),
                metric=float(overdue),
                subjects=(commitment.memory_id,),
                evidence=(
                    memory_evidence(
                        [commitment], f"Overdue by {overdue} days.", value=float(overdue)
                    ),
                ),
            )
        )
    return insights


def _aging_insights(open_items: list[StoredMemory], context: AnalysisContext) -> list[Insight]:
    insights: list[Insight] = []
    for commitment in open_items:
        meeting_date = context.memory_date(commitment)
        if not meeting_date:
            continue
        age = days_between(meeting_date, context.reference_date)
        if age < _AGING_DAYS or _is_overdue(commitment, context.reference_date) > 0:
            continue
        owner = owner_of(commitment) or "unassigned"
        insights.append(
            Insight(
                insight_id=insight_id("commitment", "aging", commitment.memory_id),
                type=InsightType.AGING_COMMITMENT,
                category=InsightCategory.COMMITMENT,
                severity=scale_severity(age, _AGING_DAYS, 90, 180),
                title=f"Commitment open for {age} days",
                detail=(
                    f"{_quote(commitment.text)} (owner: {owner}) has been open for "
                    f"{age} days without resolution."
                ),
                metric=float(age),
                subjects=(commitment.memory_id,),
                evidence=(
                    memory_evidence([commitment], f"Open for {age} days.", value=float(age)),
                ),
            )
        )
    return insights


def _resolution_insight(commitments: list[StoredMemory]) -> list[Insight]:
    total = len(commitments)
    if total < _LOW_RESOLUTION_MIN:
        return []
    resolved = sum(1 for c in commitments if c.status is MemoryStatus.RESOLVED)
    rate = resolved / total
    if rate >= _LOW_RESOLUTION:
        return []
    return [
        Insight(
            insight_id=insight_id("commitment", "resolution"),
            type=InsightType.LOW_COMMITMENT_RESOLUTION,
            category=InsightCategory.COMMITMENT,
            severity=InsightSeverity.HIGH if rate < 0.2 else InsightSeverity.MEDIUM,
            title=f"Commitment resolution rate is low ({rate:.0%})",
            detail=(
                f"Only {resolved} of {total} commitments have been resolved across "
                "the analysed meetings."
            ),
            metric=round(rate, 4),
            evidence=(
                memory_evidence(
                    commitments,
                    f"{resolved}/{total} commitments resolved.",
                    value=round(rate, 4),
                ),
            ),
        )
    ]


def _quote(text: str, limit: int = 80) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) > limit:
        collapsed = collapsed[: limit - 1].rstrip() + "\u2026"
    return f"\u201c{collapsed}\u201d"


class CommitmentInsightProvider(InsightProvider):
    """Provider exposing :func:`commitment_insights`."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="commitment-insights",
            version="1.0",
            category=InsightCategory.COMMITMENT,
            description="Commitment overload, overdue/aging items, and low resolution.",
        )

    def analyze(self, context: AnalysisContext) -> list[Insight]:
        return commitment_insights(context)


class CommitmentMetricProvider(MetricProvider):
    """Provider exposing :func:`commitment_metrics`."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="commitment-metrics",
            version="1.0",
            category=InsightCategory.COMMITMENT,
            description="Open/resolved counts, resolution rate, workload, and aging.",
        )

    def analyze(self, context: AnalysisContext) -> CommitmentMetrics:
        return commitment_metrics(context)


register_insight(CommitmentInsightProvider())
register_metric(CommitmentMetricProvider())

__all__ = [
    "CommitmentInsightProvider",
    "CommitmentMetricProvider",
    "commitment_insights",
    "commitment_metrics",
]
