"""Reusable FastAPI dependencies: database path, services, and pagination."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Query

from ...services import (
    AutomationService,
    ExportService,
    GraphService,
    IntelligenceService,
    MeetingService,
    MemoryService,
    RetrievalService,
)

DB_ENV_VAR = "MEETING_MEMORY_DB"
DEFAULT_DB = "meeting-memory.db"

MAX_PAGE_LIMIT = 500


def get_db_path() -> Path:
    """Return the SQLite database path (overridable per app/test)."""
    return Path(os.environ.get(DB_ENV_VAR, DEFAULT_DB))


DbPath = Annotated[Path, Depends(get_db_path)]


def get_meeting_service(db: DbPath) -> MeetingService:
    """Provide a :class:`MeetingService` bound to the configured database."""
    return MeetingService(db)


def get_memory_service(db: DbPath) -> MemoryService:
    """Provide a :class:`MemoryService` bound to the configured database."""
    return MemoryService(db)


def get_retrieval_service(db: DbPath) -> RetrievalService:
    """Provide a :class:`RetrievalService` bound to the configured database."""
    return RetrievalService(db)


def get_graph_service(db: DbPath) -> GraphService:
    """Provide a :class:`GraphService` bound to the configured database."""
    return GraphService(db)


def get_intelligence_service(db: DbPath) -> IntelligenceService:
    """Provide an :class:`IntelligenceService` bound to the configured database."""
    return IntelligenceService(db)


def get_automation_service(db: DbPath) -> AutomationService:
    """Provide an :class:`AutomationService` bound to the configured database."""
    return AutomationService(db)


def get_export_service(db: DbPath) -> ExportService:
    """Provide an :class:`ExportService` bound to the configured database."""
    return ExportService(db)


@dataclass(frozen=True)
class Pagination:
    """Validated pagination parameters shared by list endpoints."""

    limit: int | None
    offset: int


def pagination_params(
    limit: Annotated[int | None, Query(ge=1, le=MAX_PAGE_LIMIT)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    """Parse and validate ``limit``/``offset`` query parameters."""
    return Pagination(limit=limit, offset=offset)


MeetingServiceDep = Annotated[MeetingService, Depends(get_meeting_service)]
MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]
RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]
GraphServiceDep = Annotated[GraphService, Depends(get_graph_service)]
IntelligenceServiceDep = Annotated[IntelligenceService, Depends(get_intelligence_service)]
AutomationServiceDep = Annotated[AutomationService, Depends(get_automation_service)]
ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
PaginationDep = Annotated[Pagination, Depends(pagination_params)]
