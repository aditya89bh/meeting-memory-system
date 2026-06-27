"""Intelligence endpoints: insights, metrics, recommendations, and reports."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from ...intelligence import AnalysisFilters, InsightType
from ..dependencies import IntelligenceServiceDep, PaginationDep
from ..schemas import (
    InsightListResponse,
    InsightResponse,
    MetricsResponse,
    Pagination,
    RecommendationListResponse,
    RecommendationResponse,
    ReportResponse,
)

router = APIRouter(tags=["intelligence"])

ProjectQuery = Annotated[str | None, Query(description="Restrict analysis to one project.")]
PersonQuery = Annotated[str | None, Query(description="Restrict analysis to one person.")]
MeetingQuery = Annotated[list[str] | None, Query(description="Restrict to these meetings.")]


def _filters(project: str | None, person: str | None, meeting: list[str] | None) -> AnalysisFilters:
    return AnalysisFilters(
        project=project,
        person=person,
        meetings=frozenset(meeting) if meeting else frozenset(),
    )


@router.get("/insights", response_model=InsightListResponse, summary="Organizational insights")
def insights(
    service: IntelligenceServiceDep,
    page: PaginationDep,
    project: ProjectQuery = None,
    person: PersonQuery = None,
    meeting: MeetingQuery = None,
    insight_type: Annotated[list[InsightType] | None, Query(alias="type")] = None,
) -> InsightListResponse:
    """Return discovered insights, filtered by type and paginated."""
    report = service.report(_filters(project, person, meeting))
    found = list(report.insights)
    if insight_type is not None:
        wanted = {member.value for member in insight_type}
        found = [insight for insight in found if insight.type.value in wanted]
    total = len(found)
    window = found[page.offset : page.offset + page.limit if page.limit else None]
    items = [InsightResponse.from_domain(insight) for insight in window]
    pagination = Pagination(limit=page.limit, offset=page.offset, count=len(items), total=total)
    return InsightListResponse(pagination=pagination, items=items)


@router.get("/metrics", response_model=MetricsResponse, summary="Organizational-health metrics")
def metrics(
    service: IntelligenceServiceDep,
    project: ProjectQuery = None,
    person: PersonQuery = None,
    meeting: MeetingQuery = None,
) -> MetricsResponse:
    """Return the organizational-health snapshot."""
    health = service.metrics(_filters(project, person, meeting))
    return MetricsResponse.from_domain(health)


@router.get(
    "/recommendations",
    response_model=RecommendationListResponse,
    summary="Prioritised recommendations",
)
def recommendations(
    service: IntelligenceServiceDep,
    page: PaginationDep,
    project: ProjectQuery = None,
    person: PersonQuery = None,
    meeting: MeetingQuery = None,
) -> RecommendationListResponse:
    """Return prioritised, evidence-backed recommendations, paginated."""
    report = service.report(_filters(project, person, meeting))
    found = list(report.recommendations)
    total = len(found)
    window = found[page.offset : page.offset + page.limit if page.limit else None]
    items = [RecommendationResponse.from_domain(rec) for rec in window]
    pagination = Pagination(limit=page.limit, offset=page.offset, count=len(items), total=total)
    return RecommendationListResponse(pagination=pagination, items=items)


@router.get("/reports", response_model=ReportResponse, summary="Rendered report")
def reports(
    service: IntelligenceServiceDep,
    project: ProjectQuery = None,
    person: PersonQuery = None,
    meeting: MeetingQuery = None,
    format: Annotated[str, Query(pattern="^(json|markdown|text)$")] = "markdown",
) -> ReportResponse:
    """Render the full organizational-intelligence report in a textual format."""
    report = service.report(_filters(project, person, meeting))
    content = service.render(report, format)
    return ReportResponse.from_report(report, fmt=format, content=content)
