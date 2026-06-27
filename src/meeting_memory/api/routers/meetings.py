"""Meeting endpoints: import transcripts and read meeting records."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..dependencies import MeetingServiceDep, PaginationDep
from ..schemas import (
    ImportRequestBody,
    ImportResponse,
    MeetingListResponse,
    MeetingResponse,
    Pagination,
    StatsResponse,
)

router = APIRouter(tags=["meetings"])


@router.post(
    "/meetings/import",
    response_model=ImportResponse,
    status_code=201,
    summary="Import transcripts",
)
def import_meetings(body: ImportRequestBody, service: MeetingServiceDep) -> ImportResponse:
    """Import a transcript by server-side path or inline content.

    Provide either ``path`` (a file, directory, or ``.zip`` on the server) or
    ``content`` (inline transcript text in the given ``format``).
    """
    if body.path:
        result = service.import_path(
            body.path,
            recursive=body.recursive,
            deduplicate=body.deduplicate,
            dry_run=body.dry_run,
        )
    elif body.content is not None:
        result = service.import_content(
            body.content,
            body.format,
            deduplicate=body.deduplicate,
            dry_run=body.dry_run,
        )
    else:
        raise HTTPException(status_code=400, detail="provide either 'path' or 'content'")
    return ImportResponse.from_domain(result)


@router.get("/meetings", response_model=MeetingListResponse, summary="List meetings")
def list_meetings(service: MeetingServiceDep, page: PaginationDep) -> MeetingListResponse:
    """Return a page of stored meetings."""
    meetings = service.list_meetings(limit=page.limit, offset=page.offset)
    total = service.count_meetings()
    items = [MeetingResponse.from_domain(meeting) for meeting in meetings]
    pagination = Pagination(limit=page.limit, offset=page.offset, count=len(items), total=total)
    return MeetingListResponse(pagination=pagination, items=items)


@router.get("/meetings/stats", response_model=StatsResponse, summary="Store statistics")
def meeting_stats(service: MeetingServiceDep) -> StatsResponse:
    """Return store-wide counts by memory type and lifecycle status."""
    return StatsResponse.from_domain(service.stats())


@router.get("/meetings/{meeting_id}", response_model=MeetingResponse, summary="Get a meeting")
def get_meeting(meeting_id: str, service: MeetingServiceDep) -> MeetingResponse:
    """Return a single meeting by id."""
    return MeetingResponse.from_domain(service.get_meeting(meeting_id))
