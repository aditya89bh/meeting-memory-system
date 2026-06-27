"""Typed request/response schemas for the REST API and OpenAPI document.

Response schemas mirror the existing domain ``to_dict()`` shapes and are
populated with ``model_validate`` so they stay in lock-step with the underlying
models without duplicating serialization logic.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...connectors import ImportResult
from ...connectors.models import AutomationResult
from ...intelligence import Insight, InsightReport, OrganizationalHealth, Recommendation
from ...retrieval import RetrievalResult
from ...services import GraphSummary, MeetingStats, NeighborhoodResult
from ...storage import StoredMeeting, StoredMemory
from ..errors import ErrorResponse, ValidationErrorResponse

__all__ = [
    "AutomationRunRequest",
    "AutomationRunResponse",
    "CommitmentMetricsSchema",
    "DecisionMetricsSchema",
    "ErrorResponse",
    "EvidenceSpan",
    "GraphNodeSchema",
    "GraphResponse",
    "ImportRequestBody",
    "ImportResponse",
    "InsightEvidenceSchema",
    "InsightListResponse",
    "InsightResponse",
    "JobListResponse",
    "LogListResponse",
    "MeetingListResponse",
    "MeetingMetricsSchema",
    "MeetingResponse",
    "MemoryListResponse",
    "MemoryResponse",
    "MetricsResponse",
    "NeighborsResponse",
    "Pagination",
    "PathResponse",
    "RecommendationListResponse",
    "RecommendationResponse",
    "ReportResponse",
    "RiskMetricsSchema",
    "SearchResponse",
    "SearchResultItem",
    "StatsResponse",
    "ValidationErrorResponse",
]


class _Schema(BaseModel):
    """Base schema: ignore unknown keys so ``to_dict`` payloads validate cleanly."""

    model_config = ConfigDict(extra="ignore")


class Pagination(_Schema):
    """Pagination envelope shared by every list endpoint."""

    limit: int | None = Field(default=None, description="Requested page size.")
    offset: int = Field(default=0, description="Number of leading items skipped.")
    count: int = Field(description="Number of items returned in this page.")
    total: int = Field(description="Total number of matching items.")


# --- meetings / memories -------------------------------------------------


class EvidenceSpan(_Schema):
    """An evidence span pointing at the source utterance."""

    utterance_index: int
    start: int
    end: int
    text: str


class MeetingResponse(_Schema):
    """A stored meeting record."""

    meeting_id: str
    title: str | None = None
    date: str | None = None
    source: str | None = None
    duration_seconds: float | None = None
    participants: list[str] = Field(default_factory=list)
    transcript_hash: str
    created_at: str

    @classmethod
    def from_domain(cls, meeting: StoredMeeting) -> MeetingResponse:
        """Build the schema from a stored meeting record."""
        return cls.model_validate(meeting.to_dict())


class MemoryResponse(_Schema):
    """A stored memory record."""

    memory_id: str
    meeting_id: str
    memory_type: str
    speaker: str | None = None
    text: str
    confidence: float
    utterance_index: int
    status: str
    superseded_by: str | None = None
    content_hash: str
    created_at: str
    updated_at: str
    metadata: dict[str, str] = Field(default_factory=dict)
    evidence: list[EvidenceSpan] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, memory: StoredMemory) -> MemoryResponse:
        """Build the schema from a stored memory record."""
        return cls.model_validate(memory.to_dict())


class MeetingListResponse(_Schema):
    """A page of meetings."""

    pagination: Pagination
    items: list[MeetingResponse] = Field(default_factory=list)


class MemoryListResponse(_Schema):
    """A page of memories."""

    pagination: Pagination
    items: list[MemoryResponse] = Field(default_factory=list)


class StatsResponse(_Schema):
    """Store-wide counts by memory type and lifecycle status."""

    meetings: int
    memories: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, stats: MeetingStats) -> StatsResponse:
        """Build the schema from aggregate meeting stats."""
        return cls.model_validate(stats.to_dict())


# --- search --------------------------------------------------------------


class RetrievalStatsSchema(_Schema):
    """Counts describing a retrieval run."""

    candidates: int
    returned: int
    offset: int
    limit: int | None = None


class SearchResultItem(_Schema):
    """A single ranked search hit."""

    memory: MemoryResponse
    score: float
    explanation: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    meeting: dict[str, Any] | None = None


class SearchResponse(_Schema):
    """The full answer to a search/timeline query."""

    query: dict[str, Any] = Field(default_factory=dict)
    stats: RetrievalStatsSchema
    results: list[SearchResultItem] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, result: RetrievalResult) -> SearchResponse:
        """Build the schema from a retrieval result."""
        return cls.model_validate(result.to_dict())


# --- graph ---------------------------------------------------------------


class GraphNodeSchema(_Schema):
    """A graph node."""

    node_id: str
    node_type: str
    label: str
    ref_id: str
    created_at: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class GraphEdgeSchema(_Schema):
    """A directed, typed graph edge."""

    edge_id: str
    source_id: str
    target_id: str
    relationship: str
    created_at: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class GraphResponse(_Schema):
    """Graph counts plus an optionally filtered node listing."""

    nodes: int
    edges: int
    by_node_type: dict[str, int] = Field(default_factory=dict)
    by_relationship: dict[str, int] = Field(default_factory=dict)
    listed: list[GraphNodeSchema] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, summary: GraphSummary) -> GraphResponse:
        """Build the schema from a graph summary."""
        return cls.model_validate(summary.to_dict())


class NeighborsResponse(_Schema):
    """A node together with its traversal neighbourhood."""

    node: GraphNodeSchema
    nodes: list[GraphNodeSchema] = Field(default_factory=list)
    edges: list[GraphEdgeSchema] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, neighborhood: NeighborhoodResult) -> NeighborsResponse:
        """Build the schema from a neighbourhood result."""
        return cls.model_validate(neighborhood.to_dict())


class PathResponse(_Schema):
    """A shortest path between two nodes (``found`` is false when none exists)."""

    found: bool
    length: int = 0
    nodes: list[GraphNodeSchema] = Field(default_factory=list)
    edges: list[GraphEdgeSchema] = Field(default_factory=list)


# --- intelligence --------------------------------------------------------


class InsightEvidenceSchema(_Schema):
    """Evidence backing an insight or recommendation."""

    description: str
    memory_ids: list[str] = Field(default_factory=list)
    meeting_ids: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    value: float | None = None


class InsightResponse(_Schema):
    """A deterministic organizational insight."""

    insight_id: str
    type: str
    category: str
    severity: str
    title: str
    detail: str
    metric: float | None = None
    subjects: list[str] = Field(default_factory=list)
    evidence: list[InsightEvidenceSchema] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, insight: Insight) -> InsightResponse:
        """Build the schema from an insight."""
        return cls.model_validate(insight.to_dict())


class RecommendationResponse(_Schema):
    """A prioritised, evidence-backed recommendation."""

    recommendation_id: str
    priority: str
    category: str
    severity: str
    title: str
    detail: str
    related_memory_ids: list[str] = Field(default_factory=list)
    evidence: list[InsightEvidenceSchema] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, recommendation: Recommendation) -> RecommendationResponse:
        """Build the schema from a recommendation."""
        return cls.model_validate(recommendation.to_dict())


class InsightListResponse(_Schema):
    """A page of insights."""

    pagination: Pagination
    items: list[InsightResponse] = Field(default_factory=list)


class RecommendationListResponse(_Schema):
    """A page of recommendations."""

    pagination: Pagination
    items: list[RecommendationResponse] = Field(default_factory=list)


class DecisionMetricsSchema(_Schema):
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


class CommitmentMetricsSchema(_Schema):
    """Aggregate commitment statistics."""

    total: int = 0
    open: int = 0
    resolved: int = 0
    overdue: int = 0
    resolution_rate: float = 0.0
    avg_open_age_days: float = 0.0
    top_owner: str | None = None
    top_owner_open: int = 0


class RiskMetricsSchema(_Schema):
    """Aggregate risk statistics."""

    total: int = 0
    open: int = 0
    resolved: int = 0
    resolution_rate: float = 0.0
    recurring: int = 0
    max_recurrence: int = 0
    density: float = 0.0
    hotspot_project: str | None = None


class MeetingMetricsSchema(_Schema):
    """Aggregate meeting statistics."""

    total_meetings: int = 0
    total_memories: int = 0
    avg_memories_per_meeting: float = 0.0
    productivity: float = 0.0
    repeated_discussion_rate: float = 0.0
    span_days: int = 0


class MetricsResponse(_Schema):
    """Composite organizational-health snapshot."""

    reference_date: str
    overall: float
    scores: dict[str, float] = Field(default_factory=dict)
    decision: DecisionMetricsSchema
    commitment: CommitmentMetricsSchema
    risk: RiskMetricsSchema
    meeting: MeetingMetricsSchema

    @classmethod
    def from_domain(cls, health: OrganizationalHealth) -> MetricsResponse:
        """Build the schema from an organizational-health snapshot."""
        return cls.model_validate(health.to_dict())


class ReportResponse(_Schema):
    """A rendered organizational-intelligence report."""

    format: str
    content: str

    @classmethod
    def from_report(cls, report: InsightReport, *, fmt: str, content: str) -> ReportResponse:
        """Build the schema from a rendered report."""
        return cls(format=fmt, content=content)


# --- import / automation -------------------------------------------------


class ImportRequestBody(_Schema):
    """Request body for ``POST /meetings/import``."""

    path: str | None = Field(default=None, description="Server-side file/dir/zip path.")
    content: str | None = Field(default=None, description="Inline transcript content.")
    format: str = Field(default="text", description="Format of inline content.")
    recursive: bool = Field(default=False, description="Recurse into subdirectories.")
    deduplicate: bool = Field(default=True, description="Skip duplicate transcripts.")
    dry_run: bool = Field(default=False, description="Parse and count without writing.")


class ImportResponse(_Schema):
    """The outcome of an import request."""

    connector: str
    status: str
    files_processed: int = 0
    meetings_imported: int = 0
    memories_stored: int = 0
    duplicates: int = 0
    outcomes: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0
    correlation_id: str | None = None
    dry_run: bool = False

    @classmethod
    def from_domain(cls, result: ImportResult) -> ImportResponse:
        """Build the schema from an import result."""
        return cls.model_validate(result.to_dict())


class AutomationRunRequest(_Schema):
    """Request body for ``POST /automation/run``."""

    config: str | None = Field(default=None, description="Path to a pipeline file.")
    pipeline: dict[str, Any] | None = Field(default=None, description="Inline pipeline config.")
    dry_run: bool = Field(default=False, description="Run without writing outputs.")


class AutomationRunResponse(_Schema):
    """The outcome of an automation run."""

    job: str
    correlation_id: str
    status: str
    started_at: str
    finished_at: str
    duration_ms: float = 0.0
    stages: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    dry_run: bool = False

    @classmethod
    def from_domain(cls, result: AutomationResult) -> AutomationRunResponse:
        """Build the schema from an automation result."""
        return cls.model_validate(result.to_dict())


class JobListResponse(_Schema):
    """A page of recorded automation runs."""

    pagination: Pagination
    items: list[dict[str, Any]] = Field(default_factory=list)


class LogListResponse(_Schema):
    """A page of structured automation log records."""

    pagination: Pagination
    items: list[dict[str, Any]] = Field(default_factory=list)
