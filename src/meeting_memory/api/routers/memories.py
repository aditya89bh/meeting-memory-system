"""Memory endpoints: query and read stored memory records."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from ...extraction import MemoryType
from ...storage import MemoryQuery, MemoryStatus
from ..dependencies import MemoryServiceDep, PaginationDep
from ..schemas import MemoryListResponse, MemoryResponse, Pagination

router = APIRouter(tags=["memories"])


def _frozen(values: list[str] | None) -> frozenset[str] | None:
    return frozenset(values) if values else None


@router.get("/memories", response_model=MemoryListResponse, summary="List memories")
def list_memories(
    service: MemoryServiceDep,
    page: PaginationDep,
    memory_type: Annotated[list[MemoryType] | None, Query(alias="type")] = None,
    speaker: Annotated[list[str] | None, Query()] = None,
    meeting: Annotated[list[str] | None, Query()] = None,
    status: Annotated[list[MemoryStatus] | None, Query()] = None,
    min_confidence: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
) -> MemoryListResponse:
    """Return a page of memories filtered by the common dimensions."""
    memory_types = frozenset(member.value for member in memory_type) if memory_type else None
    statuses = frozenset(status) if status else None
    query = MemoryQuery(
        memory_types=memory_types,
        speakers=_frozen(speaker),
        meeting_ids=_frozen(meeting),
        statuses=statuses,
        min_confidence=min_confidence,
        limit=page.limit,
        offset=page.offset,
    )
    memories = service.query(query)
    total_query = MemoryQuery(
        memory_types=memory_types,
        speakers=_frozen(speaker),
        meeting_ids=_frozen(meeting),
        statuses=statuses,
        min_confidence=min_confidence,
    )
    total = service.count(total_query)
    items = [MemoryResponse.from_domain(memory) for memory in memories]
    pagination = Pagination(limit=page.limit, offset=page.offset, count=len(items), total=total)
    return MemoryListResponse(pagination=pagination, items=items)


@router.get("/memories/{memory_id}", response_model=MemoryResponse, summary="Get a memory")
def get_memory(memory_id: str, service: MemoryServiceDep) -> MemoryResponse:
    """Return a single memory by id."""
    return MemoryResponse.from_domain(service.get_memory(memory_id))
