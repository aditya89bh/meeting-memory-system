"""Organizational Intelligence Engine (Phase 6).

Discovers deterministic patterns across stored organizational memory — repeatedly
changed decisions, unresolved risks, commitment overload, project bottlenecks,
and more — and turns them into metrics, insights, recommendations, and reports.

The whole layer is deterministic and standard-library only: no LLM APIs, no
embeddings, no external analytics engines, and no external databases. Everything
is computed from the existing parser → extraction → storage → retrieval → graph
pipeline.
"""

from __future__ import annotations

from .models import (
    PRIORITY_ORDER,
    SEVERITY_ORDER,
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
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
    RiskMetrics,
)

__all__ = [
    "PRIORITY_ORDER",
    "SEVERITY_ORDER",
    "CommitmentMetrics",
    "DecisionMetrics",
    "Insight",
    "InsightCategory",
    "InsightEvidence",
    "InsightReport",
    "InsightSeverity",
    "InsightType",
    "MeetingMetrics",
    "OrganizationalHealth",
    "PersonMetrics",
    "ProjectMetrics",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationPriority",
    "RiskMetrics",
]
