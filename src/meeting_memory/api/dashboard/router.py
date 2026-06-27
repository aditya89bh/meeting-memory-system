"""Server-rendered dashboard routes (Overview, Meetings, Search, Graph, ...)."""

from __future__ import annotations

from html import escape
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from ...intelligence import AnalysisFilters
from ...retrieval import RetrievalQuery
from ..dependencies import (
    AutomationServiceDep,
    GraphServiceDep,
    IntelligenceServiceDep,
    MeetingServiceDep,
    RetrievalServiceDep,
)
from . import render

router = APIRouter(tags=["dashboard"], include_in_schema=False)


@router.get("/", response_class=RedirectResponse)
def home() -> RedirectResponse:
    """Redirect the site root to the dashboard overview."""
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
def overview(
    meetings: MeetingServiceDep,
    graph: GraphServiceDep,
    intelligence: IntelligenceServiceDep,
    automation: AutomationServiceDep,
) -> HTMLResponse:
    """Render the overview page with store-wide counts and health."""
    stats = meetings.stats()
    summary = graph.summary()
    health = intelligence.metrics()
    jobs = automation.jobs()
    body = render.section("Overview")
    body += render.cards(
        [
            ("Meetings", stats.meetings),
            ("Memories", stats.memories),
            ("Graph nodes", summary.nodes),
            ("Graph edges", summary.edges),
            ("Health", f"{health.overall:.2f}"),
            ("Automation runs", len(jobs)),
        ]
    )
    body += render.section("Memories by type")
    body += render.table(
        ["Type", "Count"], [(key, value) for key, value in sorted(stats.by_type.items())]
    )
    body += render.section("Memories by status")
    body += render.table(
        ["Status", "Count"], [(key, value) for key, value in sorted(stats.by_status.items())]
    )
    return HTMLResponse(render.layout("Overview", "Overview", body))


@router.get("/dashboard/meetings", response_class=HTMLResponse)
def meetings_page(
    service: MeetingServiceDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> HTMLResponse:
    """Render a table of stored meetings."""
    meetings = service.list_meetings(limit=limit)
    rows = [
        (
            meeting.meeting_id,
            meeting.title or "(untitled)",
            meeting.date or "-",
            ", ".join(meeting.participants) or "-",
        )
        for meeting in meetings
    ]
    body = render.section("Meetings")
    body += render.table(["ID", "Title", "Date", "Participants"], rows)
    return HTMLResponse(render.layout("Meetings", "Meetings", body))


@router.get("/dashboard/search", response_class=HTMLResponse)
def search_page(
    service: RetrievalServiceDep,
    q: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    """Render the search form and, when a query is given, its ranked results."""
    body = render.section("Search")
    term = q.strip() if q else ""
    body += (
        '<form class="search" method="get" action="/dashboard/search">'
        f'<input type="text" name="q" placeholder="Search organizational memory..." '
        f'value="{escape(term)}">'
        '<button type="submit">Search</button></form>'
    )
    if term:
        result = service.search(RetrievalQuery(text=term, limit=50, context_size=0))
        rows = [
            (
                f"{ranked.score:.3f}",
                ranked.memory.memory_type,
                ranked.memory.speaker or "?",
                ranked.memory.text,
            )
            for ranked in result.ranked
        ]
        body += render.section(f"{len(result.ranked)} result(s)")
        body += render.table(["Score", "Type", "Speaker", "Text"], rows)
    return HTMLResponse(render.layout("Search", "Search", body))


@router.get("/dashboard/graph", response_class=HTMLResponse)
def graph_page(
    service: GraphServiceDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> HTMLResponse:
    """Render graph counts and a sample of nodes."""
    summary = service.summary(limit=limit)
    body = render.section("Knowledge graph")
    body += render.cards([("Nodes", summary.nodes), ("Edges", summary.edges)])
    body += render.section("Nodes by type")
    body += render.table(
        ["Type", "Count"], [(key, value) for key, value in sorted(summary.by_node_type.items())]
    )
    body += render.section("Relationships")
    body += render.table(
        ["Relationship", "Count"],
        [(key, value) for key, value in sorted(summary.by_relationship.items())],
    )
    body += render.section("Nodes")
    rows = [(node.node_id, node.node_type.value, node.label) for node in summary.listed]
    body += render.table(["ID", "Type", "Label"], rows)
    return HTMLResponse(render.layout("Graph", "Graph", body))


@router.get("/dashboard/insights", response_class=HTMLResponse)
def insights_page(service: IntelligenceServiceDep) -> HTMLResponse:
    """Render discovered insights and recommendations."""
    report = service.report(AnalysisFilters())
    body = render.section("Insights")
    body += render.table(
        ["Severity", "Type", "Title", "Detail"],
        [
            (insight.severity.value, insight.type.value, insight.title, insight.detail)
            for insight in report.insights
        ],
    )
    body += render.section("Recommendations")
    body += render.table(
        ["Priority", "Title", "Detail"],
        [(rec.priority.value, rec.title, rec.detail) for rec in report.recommendations],
    )
    return HTMLResponse(render.layout("Insights", "Insights", body))


@router.get("/dashboard/reports", response_class=HTMLResponse)
def reports_page(service: IntelligenceServiceDep) -> HTMLResponse:
    """Render the full intelligence report as Markdown text."""
    report = service.report(AnalysisFilters())
    content = service.render(report, "markdown")
    body = render.section("Organizational report")
    body += f"<pre>{escape(content)}</pre>"
    return HTMLResponse(render.layout("Reports", "Reports", body))


@router.get("/dashboard/jobs", response_class=HTMLResponse)
def jobs_page(service: AutomationServiceDep) -> HTMLResponse:
    """Render recorded automation runs and recent log lines."""
    jobs = service.jobs()
    body = render.section("Automation runs")
    job_rows = []
    for job in jobs:
        stages = job.get("stages")
        stage_count = len(stages) if isinstance(stages, list) else 0
        job_rows.append(
            (
                str(job.get("started_at", "-")),
                str(job.get("job", "-")),
                str(job.get("status", "-")),
                stage_count,
                str(job.get("correlation_id", "-")),
            )
        )
    body += render.table(["Started", "Job", "Status", "Stages", "Correlation"], job_rows)
    logs = service.logs(limit=20)
    body += render.section("Recent logs")
    body += render.table(
        ["Level", "Stage", "Message"],
        [
            (
                str(log.get("level", "-")),
                str(log.get("stage") or "-"),
                str(log.get("message", "")),
            )
            for log in logs
        ],
    )
    return HTMLResponse(render.layout("Jobs", "Jobs", body))
