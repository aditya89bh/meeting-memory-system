"""Deterministic recommendation engine.

Turns discovered insights into actionable, evidence-backed recommendations using
a fixed mapping from insight type to a suggested action. Priority is derived
from insight severity, and supporting evidence and related memories are carried
straight through, so recommendations are fully reproducible.
"""

from __future__ import annotations

from .analysis import insight_id
from .context import AnalysisContext
from .health import meeting_metrics
from .models import (
    Insight,
    InsightCategory,
    InsightSeverity,
    InsightType,
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
)
from .providers import ProviderMetadata, RecommendationProvider
from .registry import register_recommendation

# Productivity below which the meeting cadence is flagged as ineffective.
_INEFFECTIVE_PRODUCTIVITY = 0.5
_MIN_MEETINGS_FOR_CADENCE = 3

_SEVERITY_TO_PRIORITY: dict[InsightSeverity, RecommendationPriority] = {
    InsightSeverity.CRITICAL: RecommendationPriority.URGENT,
    InsightSeverity.HIGH: RecommendationPriority.HIGH,
    InsightSeverity.MEDIUM: RecommendationPriority.MEDIUM,
    InsightSeverity.LOW: RecommendationPriority.LOW,
    InsightSeverity.INFO: RecommendationPriority.LOW,
}

_CATEGORY_MAP: dict[InsightCategory, RecommendationCategory] = {
    InsightCategory.DECISION: RecommendationCategory.DECISION,
    InsightCategory.COMMITMENT: RecommendationCategory.COMMITMENT,
    InsightCategory.RISK: RecommendationCategory.RISK,
    InsightCategory.MEETING: RecommendationCategory.MEETING,
    InsightCategory.PROJECT: RecommendationCategory.PROJECT,
    InsightCategory.PERSON: RecommendationCategory.PERSON,
    InsightCategory.ORGANIZATION: RecommendationCategory.ORGANIZATION,
}

# Action title + advice per insight type.
_ACTIONS: dict[InsightType, tuple[str, str]] = {
    InsightType.REPEATEDLY_SUPERSEDED_DECISION: (
        "Stabilize a repeatedly changed decision",
        "Hold a focused review to finalize this decision and record the rationale.",
    ),
    InsightType.REVISITED_DECISION: (
        "Settle a repeatedly revisited decision",
        "Assign a clear owner and close the topic with a documented outcome.",
    ),
    InsightType.LONG_RUNNING_DECISION: (
        "Close out a long-running decision",
        "Set a decision deadline to stop the lineage from dragging on.",
    ),
    InsightType.UNSTABLE_DECISIONS: (
        "Improve overall decision stability",
        "Review how decisions are made and recorded to reduce churn.",
    ),
    InsightType.OPEN_COMMITMENT_OVERLOAD: (
        "Rebalance an overloaded owner",
        "Redistribute or de-scope commitments to relieve the bottleneck.",
    ),
    InsightType.OVERDUE_COMMITMENT: (
        "Follow up on an overdue commitment",
        "Confirm a new due date or re-assign the work.",
    ),
    InsightType.AGING_COMMITMENT: (
        "Review an aging commitment",
        "Check whether the commitment is still relevant and set a due date.",
    ),
    InsightType.LOW_COMMITMENT_RESOLUTION: (
        "Improve commitment follow-through",
        "Track commitments to completion in each meeting's review.",
    ),
    InsightType.RECURRING_RISK: (
        "Mitigate a recurring risk",
        "Create an owned mitigation plan so the risk stops resurfacing.",
    ),
    InsightType.UNRESOLVED_RISK: (
        "Resolve a long-standing risk",
        "Escalate the risk and assign an owner with a resolution target.",
    ),
    InsightType.LONG_LIVED_RISK: (
        "Address a persistent risk",
        "Re-evaluate the mitigation; the current approach is not closing it.",
    ),
    InsightType.RISK_HOTSPOT: (
        "Reduce risk concentration on a project",
        "Run a risk review for this project to address clustered risks.",
    ),
    InsightType.PROJECT_BLOCKER: (
        "Unblock a project",
        "Prioritize clearing the recurring blockers on this project.",
    ),
}


def recommendations_from(insights: list[Insight]) -> list[Recommendation]:
    """Map insights onto deterministic recommendations."""
    result: list[Recommendation] = []
    for insight in insights:
        action = _ACTIONS.get(insight.type)
        if action is None:
            continue
        title, advice = action
        related = tuple(
            dict.fromkeys(memory_id for ev in insight.evidence for memory_id in ev.memory_ids)
        )
        result.append(
            Recommendation(
                recommendation_id=insight_id("rec", insight.insight_id),
                priority=_SEVERITY_TO_PRIORITY[insight.severity],
                category=_CATEGORY_MAP[insight.category],
                severity=insight.severity,
                title=title,
                detail=f"{advice} {insight.detail}",
                related_memory_ids=related,
                evidence=insight.evidence,
            )
        )
    return result


def cadence_recommendation(context: AnalysisContext) -> list[Recommendation]:
    """Flag an ineffective meeting cadence based on meeting productivity."""
    metrics = meeting_metrics(context)
    if (
        metrics.total_meetings < _MIN_MEETINGS_FOR_CADENCE
        or metrics.productivity >= _INEFFECTIVE_PRODUCTIVITY
    ):
        return []
    return [
        Recommendation(
            recommendation_id=insight_id("rec", "meeting", "cadence"),
            priority=RecommendationPriority.MEDIUM,
            category=RecommendationCategory.MEETING,
            severity=InsightSeverity.MEDIUM,
            title="Meeting cadence appears ineffective",
            detail=(
                f"Across {metrics.total_meetings} meetings only "
                f"{metrics.productivity:.2f} decisions/commitments were produced per "
                "meeting; consider tightening agendas or cadence."
            ),
        )
    ]


class InsightRecommendationProvider(RecommendationProvider):
    """Provider turning insights (and cadence) into recommendations."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="insight-recommendations",
            version="1.0",
            category=InsightCategory.ORGANIZATION,
            description="Maps insights and meeting cadence onto actionable advice.",
        )

    def analyze(self, context: AnalysisContext, insights: list[Insight]) -> list[Recommendation]:
        return recommendations_from(insights) + cadence_recommendation(context)


register_recommendation(InsightRecommendationProvider())

__all__ = [
    "InsightRecommendationProvider",
    "cadence_recommendation",
    "recommendations_from",
]
