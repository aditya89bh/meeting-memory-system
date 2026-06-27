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

from .commitment import commitment_insights, commitment_metrics
from .context import AnalysisContext, AnalysisFilters, build_context, owner_of
from .decision import decision_insights, decision_metrics
from .engine import IntelligenceEngine
from .health import meeting_metrics
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
from .providers import (
    InsightProvider,
    MetricProvider,
    Provider,
    ProviderMetadata,
    RecommendationProvider,
    ReportProvider,
)
from .recommendations import cadence_recommendation, recommendations_from
from .registry import (
    ProviderSet,
    default_providers,
    register_insight,
    register_metric,
    register_recommendation,
    register_report,
)
from .report import (
    REPORT_FORMATS,
    render_report,
    to_json,
    to_markdown,
    to_text,
)
from .risk import risk_insights, risk_metrics

__all__ = [
    "PRIORITY_ORDER",
    "REPORT_FORMATS",
    "SEVERITY_ORDER",
    "AnalysisContext",
    "AnalysisFilters",
    "CommitmentMetrics",
    "DecisionMetrics",
    "Insight",
    "InsightCategory",
    "InsightEvidence",
    "InsightProvider",
    "InsightReport",
    "InsightSeverity",
    "InsightType",
    "IntelligenceEngine",
    "MeetingMetrics",
    "MetricProvider",
    "OrganizationalHealth",
    "PersonMetrics",
    "ProjectMetrics",
    "Provider",
    "ProviderMetadata",
    "ProviderSet",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationPriority",
    "RecommendationProvider",
    "ReportProvider",
    "RiskMetrics",
    "build_context",
    "cadence_recommendation",
    "commitment_insights",
    "commitment_metrics",
    "decision_insights",
    "decision_metrics",
    "default_providers",
    "meeting_metrics",
    "owner_of",
    "recommendations_from",
    "register_insight",
    "register_metric",
    "register_recommendation",
    "register_report",
    "render_report",
    "risk_insights",
    "risk_metrics",
    "to_json",
    "to_markdown",
    "to_text",
]
