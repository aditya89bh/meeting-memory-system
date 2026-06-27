"""Typed models for the organizational intelligence engine (Phase 6).

Every model is an immutable, JSON-serialisable value object. Insights, metrics,
recommendations, and the assembled report are all *computed* deterministically
from stored organizational memory — nothing here fabricates data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InsightSeverity(str, Enum):
    """How much attention an insight likely warrants."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


# Deterministic ordering for severities (low to high) used when sorting.
SEVERITY_ORDER: dict[InsightSeverity, int] = {
    InsightSeverity.INFO: 0,
    InsightSeverity.LOW: 1,
    InsightSeverity.MEDIUM: 2,
    InsightSeverity.HIGH: 3,
    InsightSeverity.CRITICAL: 4,
}


class InsightCategory(str, Enum):
    """The organizational domain an insight or metric belongs to."""

    DECISION = "decision"
    COMMITMENT = "commitment"
    RISK = "risk"
    MEETING = "meeting"
    PROJECT = "project"
    PERSON = "person"
    ORGANIZATION = "organization"

    def __str__(self) -> str:
        return self.value


class InsightType(str, Enum):
    """The specific pattern an insight represents."""

    REPEATEDLY_SUPERSEDED_DECISION = "repeatedly_superseded_decision"
    REVISITED_DECISION = "revisited_decision"
    LONG_RUNNING_DECISION = "long_running_decision"
    UNSTABLE_DECISIONS = "unstable_decisions"
    OPEN_COMMITMENT_OVERLOAD = "open_commitment_overload"
    OVERDUE_COMMITMENT = "overdue_commitment"
    LOW_COMMITMENT_RESOLUTION = "low_commitment_resolution"
    AGING_COMMITMENT = "aging_commitment"
    RECURRING_RISK = "recurring_risk"
    UNRESOLVED_RISK = "unresolved_risk"
    LONG_LIVED_RISK = "long_lived_risk"
    RISK_HOTSPOT = "risk_hotspot"
    REPEATED_DISCUSSION = "repeated_discussion"
    PROJECT_BLOCKER = "project_blocker"
    ASSUMPTION_BECAME_FACT = "assumption_became_fact"

    def __str__(self) -> str:
        return self.value


class RecommendationPriority(str, Enum):
    """How urgently a recommendation should be acted on."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    def __str__(self) -> str:
        return self.value


PRIORITY_ORDER: dict[RecommendationPriority, int] = {
    RecommendationPriority.LOW: 0,
    RecommendationPriority.MEDIUM: 1,
    RecommendationPriority.HIGH: 2,
    RecommendationPriority.URGENT: 3,
}


class RecommendationCategory(str, Enum):
    """The organizational domain a recommendation addresses."""

    DECISION = "decision"
    COMMITMENT = "commitment"
    RISK = "risk"
    MEETING = "meeting"
    PROJECT = "project"
    PERSON = "person"
    ORGANIZATION = "organization"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class InsightEvidence:
    """A single piece of supporting evidence for an insight or recommendation."""

    description: str
    memory_ids: tuple[str, ...] = ()
    meeting_ids: tuple[str, ...] = ()
    node_ids: tuple[str, ...] = ()
    value: float | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the evidence into JSON-compatible primitives."""
        return {
            "description": self.description,
            "memory_ids": list(self.memory_ids),
            "meeting_ids": list(self.meeting_ids),
            "node_ids": list(self.node_ids),
            "value": self.value,
        }


@dataclass(frozen=True)
class Insight:
    """A deterministic observation about the organization's memory."""

    insight_id: str
    type: InsightType
    category: InsightCategory
    severity: InsightSeverity
    title: str
    detail: str
    metric: float | None = None
    subjects: tuple[str, ...] = ()
    evidence: tuple[InsightEvidence, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialise the insight into JSON-compatible primitives."""
        return {
            "insight_id": self.insight_id,
            "type": self.type.value,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "metric": self.metric,
            "subjects": list(self.subjects),
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class Recommendation:
    """A deterministic, evidence-backed recommendation."""

    recommendation_id: str
    priority: RecommendationPriority
    category: RecommendationCategory
    severity: InsightSeverity
    title: str
    detail: str
    related_memory_ids: tuple[str, ...] = ()
    evidence: tuple[InsightEvidence, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Serialise the recommendation into JSON-compatible primitives."""
        return {
            "recommendation_id": self.recommendation_id,
            "priority": self.priority.value,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "related_memory_ids": list(self.related_memory_ids),
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class DecisionMetrics:
    """Aggregate decision statistics."""

    total: int = 0
    active: int = 0
    superseded: int = 0
    revisited: int = 0
    stability: float = 0.0
    density: float = 0.0
    velocity_per_week: float = 0.0
    distinct_owners: int = 0
    top_owner: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the decision metrics."""
        return {
            "total": self.total,
            "active": self.active,
            "superseded": self.superseded,
            "revisited": self.revisited,
            "stability": self.stability,
            "density": self.density,
            "velocity_per_week": self.velocity_per_week,
            "distinct_owners": self.distinct_owners,
            "top_owner": self.top_owner,
        }


@dataclass(frozen=True)
class CommitmentMetrics:
    """Aggregate commitment statistics."""

    total: int = 0
    open: int = 0
    resolved: int = 0
    overdue: int = 0
    resolution_rate: float = 0.0
    avg_open_age_days: float = 0.0
    top_owner: str | None = None
    top_owner_open: int = 0

    def to_dict(self) -> dict[str, object]:
        """Serialise the commitment metrics."""
        return {
            "total": self.total,
            "open": self.open,
            "resolved": self.resolved,
            "overdue": self.overdue,
            "resolution_rate": self.resolution_rate,
            "avg_open_age_days": self.avg_open_age_days,
            "top_owner": self.top_owner,
            "top_owner_open": self.top_owner_open,
        }


@dataclass(frozen=True)
class RiskMetrics:
    """Aggregate risk statistics."""

    total: int = 0
    open: int = 0
    resolved: int = 0
    resolution_rate: float = 0.0
    recurring: int = 0
    max_recurrence: int = 0
    density: float = 0.0
    hotspot_project: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the risk metrics."""
        return {
            "total": self.total,
            "open": self.open,
            "resolved": self.resolved,
            "resolution_rate": self.resolution_rate,
            "recurring": self.recurring,
            "max_recurrence": self.max_recurrence,
            "density": self.density,
            "hotspot_project": self.hotspot_project,
        }


@dataclass(frozen=True)
class MeetingMetrics:
    """Aggregate meeting statistics."""

    total_meetings: int = 0
    total_memories: int = 0
    avg_memories_per_meeting: float = 0.0
    productivity: float = 0.0
    repeated_discussion_rate: float = 0.0
    span_days: int = 0

    def to_dict(self) -> dict[str, object]:
        """Serialise the meeting metrics."""
        return {
            "total_meetings": self.total_meetings,
            "total_memories": self.total_memories,
            "avg_memories_per_meeting": self.avg_memories_per_meeting,
            "productivity": self.productivity,
            "repeated_discussion_rate": self.repeated_discussion_rate,
            "span_days": self.span_days,
        }


@dataclass(frozen=True)
class ProjectMetrics:
    """Per-project statistics derived from the graph and memories."""

    project_id: str
    name: str
    risk_count: int = 0
    decision_count: int = 0
    meeting_count: int = 0
    blocker_count: int = 0

    def to_dict(self) -> dict[str, object]:
        """Serialise the project metrics."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "risk_count": self.risk_count,
            "decision_count": self.decision_count,
            "meeting_count": self.meeting_count,
            "blocker_count": self.blocker_count,
        }


@dataclass(frozen=True)
class PersonMetrics:
    """Per-person statistics derived from memories."""

    name: str
    open_commitments: int = 0
    total_commitments: int = 0
    decisions_owned: int = 0
    meetings_attended: int = 0

    def to_dict(self) -> dict[str, object]:
        """Serialise the person metrics."""
        return {
            "name": self.name,
            "open_commitments": self.open_commitments,
            "total_commitments": self.total_commitments,
            "decisions_owned": self.decisions_owned,
            "meetings_attended": self.meetings_attended,
        }


@dataclass(frozen=True)
class OrganizationalHealth:
    """Composite organizational-health snapshot."""

    reference_date: str
    decision: DecisionMetrics
    commitment: CommitmentMetrics
    risk: RiskMetrics
    meeting: MeetingMetrics
    scores: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0

    def to_dict(self) -> dict[str, object]:
        """Serialise the organizational-health snapshot."""
        return {
            "reference_date": self.reference_date,
            "overall": self.overall,
            "scores": dict(self.scores),
            "decision": self.decision.to_dict(),
            "commitment": self.commitment.to_dict(),
            "risk": self.risk.to_dict(),
            "meeting": self.meeting.to_dict(),
        }


@dataclass(frozen=True)
class InsightReport:
    """The full organizational-intelligence report."""

    reference_date: str
    health: OrganizationalHealth
    insights: tuple[Insight, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()
    projects: tuple[ProjectMetrics, ...] = ()
    people: tuple[PersonMetrics, ...] = ()

    def insights_by_category(self, category: InsightCategory) -> list[Insight]:
        """Return insights in a single category, preserving order."""
        return [insight for insight in self.insights if insight.category is category]

    def to_dict(self) -> dict[str, object]:
        """Serialise the whole report into JSON-compatible primitives."""
        return {
            "reference_date": self.reference_date,
            "health": self.health.to_dict(),
            "insights": [insight.to_dict() for insight in self.insights],
            "recommendations": [rec.to_dict() for rec in self.recommendations],
            "projects": [project.to_dict() for project in self.projects],
            "people": [person.to_dict() for person in self.people],
        }
