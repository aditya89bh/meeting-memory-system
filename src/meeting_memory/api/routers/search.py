"""Retrieval endpoint: ranked keyword/metadata search over stored memory."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from ...extraction import MemoryType
from ...retrieval import RetrievalQuery
from ...storage import MemoryStatus
from ..dependencies import RetrievalServiceDep
from ..schemas import SearchResponse

router = APIRouter(tags=["search"])

_ORDERS = ("relevance", "chronological", "reverse-chronological")


@router.get("/search", response_model=SearchResponse, summary="Search memories")
def search(
    service: RetrievalServiceDep,
    q: Annotated[str | None, Query(description="Free-text query terms.")] = None,
    memory_type: Annotated[list[MemoryType] | None, Query(alias="type")] = None,
    speaker: Annotated[list[str] | None, Query()] = None,
    status: Annotated[list[MemoryStatus] | None, Query()] = None,
    meeting: Annotated[list[str] | None, Query()] = None,
    min_confidence: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    order: Annotated[str, Query(pattern="^(relevance|chronological|reverse-chronological)$")] = (
        "relevance"
    ),
    context_size: Annotated[int, Query(ge=0, le=10)] = 1,
    limit: Annotated[int | None, Query(ge=1, le=500)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchResponse:
    """Run a deterministic ranked retrieval query and return scored results."""
    memory_types = (
        frozenset(member.value for member in memory_type) if memory_type else frozenset()
    )
    query = RetrievalQuery(
        text=q.strip() if q and q.strip() else None,
        memory_types=memory_types,
        speakers=frozenset(speaker) if speaker else frozenset(),
        statuses=frozenset(status) if status else frozenset(),
        meeting_ids=frozenset(meeting) if meeting else frozenset(),
        min_confidence=min_confidence,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        context_size=context_size,
        order=order,
    )
    result = service.search(query)
    return SearchResponse.from_domain(result)
