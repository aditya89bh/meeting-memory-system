"""Automation endpoints: run pipelines and read job history and logs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from ..dependencies import AutomationServiceDep, PaginationDep
from ..schemas import (
    AutomationRunRequest,
    AutomationRunResponse,
    JobListResponse,
    LogListResponse,
    Pagination,
)

router = APIRouter(prefix="/automation", tags=["automation"])


@router.post("/run", response_model=AutomationRunResponse, summary="Run an automation pipeline")
def run_pipeline(
    body: AutomationRunRequest, service: AutomationServiceDep
) -> AutomationRunResponse:
    """Run a declarative pipeline by server-side path or inline configuration.

    Provide either ``config`` (a path to a YAML/JSON pipeline file on the server)
    or ``pipeline`` (an inline pipeline mapping). The pipeline is validated before
    execution; ``dry_run`` runs every stage without writing outputs.
    """
    if body.config:
        result = service.run_file(body.config, dry_run=body.dry_run)
    elif body.pipeline is not None:
        result = service.run_config(body.pipeline, dry_run=body.dry_run)
    else:
        raise HTTPException(status_code=400, detail="provide either 'config' or 'pipeline'")
    return AutomationRunResponse.from_domain(result)


@router.get("/jobs", response_model=JobListResponse, summary="List recorded runs")
def list_jobs(service: AutomationServiceDep, page: PaginationDep) -> JobListResponse:
    """Return recorded automation runs (most recent first), paginated."""
    records = service.jobs()
    total = len(records)
    window = records[page.offset : page.offset + page.limit if page.limit else None]
    pagination = Pagination(limit=page.limit, offset=page.offset, count=len(window), total=total)
    return JobListResponse(pagination=pagination, items=window)


@router.get("/logs", response_model=LogListResponse, summary="Read structured logs")
def list_logs(
    service: AutomationServiceDep,
    page: PaginationDep,
    correlation_id: Annotated[str | None, Query(description="Filter by correlation id.")] = None,
) -> LogListResponse:
    """Return structured automation logs, optionally filtered by correlation id."""
    records: list[dict[str, Any]] = service.logs(correlation_id=correlation_id)
    total = len(records)
    window = records[page.offset : page.offset + page.limit if page.limit else None]
    pagination = Pagination(limit=page.limit, offset=page.offset, count=len(window), total=total)
    return LogListResponse(pagination=pagination, items=window)
