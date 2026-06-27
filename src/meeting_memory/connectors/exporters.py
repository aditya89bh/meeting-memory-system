"""Deterministic export connectors (Phase 7).

Exporters turn stored organizational memory and intelligence into shareable
artifacts. They reuse the existing layers end to end: the report exporters run
the :class:`~meeting_memory.intelligence.IntelligenceEngine` over the store (and a
freshly built in-memory graph), the graph exporter reuses
:func:`~meeting_memory.graph.build_graph` and the graph export renderers, and the
CSV/summary exporters read straight from the store.

Each exporter validates its request, supports a ``dry_run`` that renders without
writing, returns the rendered content (for stdout or previews), and writes UTF-8
to a destination file when one is given.
"""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path

from ..graph import (
    GraphEdge,
    GraphNode,
    GraphStore,
    SQLiteGraphStore,
    build_graph,
    export_graph,
)
from ..intelligence import InsightCategory, InsightReport, IntelligenceEngine, render_report
from ..storage.base import MemoryStore
from .base import ConnectorRegistry, ExportConnector
from .logging import LogLevel, StructuredLogger
from .models import (
    ConnectorCapability,
    ConnectorMetadata,
    ConnectorStatus,
    ConnectorType,
    ExportRequest,
    ExportResult,
)

CONNECTOR_VERSION = "1.0"

_GRAPH_FORMATS = {"graph": "json", "mermaid": "mermaid", "dot": "dot"}


def _report_from_store(store: MemoryStore) -> InsightReport:
    """Build an :class:`InsightReport` from the store and a fresh in-memory graph."""
    graph = SQLiteGraphStore(":memory:")
    try:
        return IntelligenceEngine().analyze(store, graph)
    finally:
        graph.close()


def _graph_data(
    store: MemoryStore, graph_store: GraphStore | None
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Return ``(nodes, edges)``, building a fresh in-memory graph when needed."""
    if graph_store is not None:
        return list(graph_store.list_nodes()), list(graph_store.list_edges())
    graph = SQLiteGraphStore(":memory:")
    try:
        build_graph(store, graph)
        return list(graph.list_nodes()), list(graph.list_edges())
    finally:
        graph.close()


def report_to_html(report: InsightReport) -> str:
    """Render an :class:`InsightReport` as a self-contained, deterministic HTML page."""
    health = report.health
    lines: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Organizational Intelligence Report</title>",
        "</head>",
        "<body>",
        "<h1>Organizational Intelligence Report</h1>",
        f"<p>Reference date: {html.escape(report.reference_date or 'n/a')}</p>",
        "<h2>Executive summary</h2>",
        "<ul>",
        f"<li>Overall health: {health.overall:.2f}</li>",
        f"<li>Insights: {len(report.insights)}</li>",
        f"<li>Recommendations: {len(report.recommendations)}</li>",
        "</ul>",
        "<h2>Organizational health</h2>",
        "<table>",
        "<tr><th>Score</th><th>Value</th></tr>",
    ]
    for key in sorted(health.scores):
        lines.append(f"<tr><td>{html.escape(key)}</td><td>{health.scores[key]:.4g}</td></tr>")
    lines.append("</table>")

    for title, category in (
        ("Decision insights", InsightCategory.DECISION),
        ("Commitment insights", InsightCategory.COMMITMENT),
        ("Risk insights", InsightCategory.RISK),
    ):
        lines.append(f"<h2>{title}</h2>")
        section = report.insights_by_category(category)
        if not section:
            lines.append("<p>None</p>")
            continue
        lines.append("<ul>")
        for insight in section:
            lines.append(
                f"<li><strong>[{html.escape(str(insight.severity))}] "
                f"{html.escape(insight.title)}</strong> — {html.escape(insight.detail)}</li>"
            )
        lines.append("</ul>")

    lines.append("<h2>Recommendations</h2>")
    if not report.recommendations:
        lines.append("<p>None</p>")
    else:
        lines.append("<ul>")
        for rec in report.recommendations:
            lines.append(
                f"<li><strong>[{html.escape(str(rec.priority))}] "
                f"{html.escape(rec.title)}</strong> — {html.escape(rec.detail)}</li>"
            )
        lines.append("</ul>")

    lines.extend(["</body>", "</html>"])
    return "\n".join(lines) + "\n"


def _memories_to_csv(store: MemoryStore) -> tuple[str, int]:
    """Render all stored memories as deterministic CSV; return ``(text, count)``."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["memory_id", "meeting_id", "type", "status", "speaker", "confidence", "text"])
    memories = sorted(store.list(), key=lambda memory: memory.memory_id)
    for memory in memories:
        writer.writerow(
            [
                memory.memory_id,
                memory.meeting_id,
                memory.memory_type,
                memory.status.value,
                memory.speaker or "",
                f"{memory.confidence:.4f}",
                memory.text,
            ]
        )
    return buffer.getvalue(), len(memories)


def _meeting_summaries(store: MemoryStore) -> tuple[str, int]:
    """Render per-meeting markdown summaries; return ``(text, meeting_count)``."""
    meetings = store.list_meetings()
    lines: list[str] = ["# Meeting summaries", ""]
    for meeting in meetings:
        memories = sorted(
            store.find_by_meeting(meeting.meeting_id),
            key=lambda memory: (memory.memory_type, memory.memory_id),
        )
        title = meeting.title or "(untitled)"
        lines.append(f"## {title} ({meeting.meeting_id})")
        lines.append(f"- date: {meeting.date or 'n/a'}")
        lines.append(f"- participants: {', '.join(meeting.participants) or 'n/a'}")
        lines.append(f"- memories: {len(memories)}")
        for memory in memories:
            speaker = memory.speaker or "?"
            lines.append(f"  - [{memory.memory_type}] {speaker}: {memory.text}")
        lines.append("")
    return "\n".join(lines), len(meetings)


class _BaseExportConnector(ExportConnector):
    """Shared validation, writing, and logging for export connectors."""

    name_id: str
    formats: tuple[str, ...]
    capabilities: frozenset[ConnectorCapability] = frozenset(
        {ConnectorCapability.VALIDATION, ConnectorCapability.DRY_RUN}
    )
    summary: str

    def metadata(self) -> ConnectorMetadata:
        """Describe this export connector."""
        return ConnectorMetadata(
            name=self.name_id,
            version=CONNECTOR_VERSION,
            connector_type=ConnectorType.EXPORT,
            description=self.summary,
            capabilities=self.capabilities,
            formats=self.formats,
        )

    def validate(self, request: ExportRequest) -> list[str]:
        """Validate the requested format and destination parent directory."""
        problems: list[str] = []
        if request.fmt.lower() not in self.formats:
            problems.append(
                f"{self.name_id} does not support format {request.fmt!r} "
                f"(supported: {', '.join(self.formats)})"
            )
        if request.destination is not None:
            parent = Path(request.destination).parent
            if parent and not parent.exists() and str(parent) not in ("", "."):
                problems.append(f"destination directory does not exist: {parent}")
        return problems

    def _render(
        self,
        request: ExportRequest,
        store: MemoryStore,
        graph_store: GraphStore | None,
    ) -> tuple[str, int]:
        """Produce ``(content, item_count)`` for the request. Overridden per format."""
        raise NotImplementedError

    def _emit(
        self,
        request: ExportRequest,
        *,
        content: str,
        items: int,
        dry_run: bool,
        logger: StructuredLogger | None,
    ) -> ExportResult:
        start = logger.mark() if logger is not None else 0.0
        bytes_written = 0
        if not dry_run and request.destination is not None:
            path = Path(request.destination)
            if path.parent and str(path.parent) not in ("", "."):
                path.parent.mkdir(parents=True, exist_ok=True)
            text = content if content.endswith("\n") else content + "\n"
            path.write_text(text, encoding="utf-8")
            bytes_written = len(text.encode("utf-8"))
        status = ConnectorStatus.DRY_RUN if dry_run else ConnectorStatus.SUCCESS
        duration = logger.elapsed(start) if logger is not None else 0.0
        result = ExportResult(
            connector=self.name_id,
            status=status,
            fmt=request.fmt,
            destination=request.destination,
            items_exported=items,
            bytes_written=bytes_written,
            content=content,
            duration_ms=duration,
            correlation_id=logger.correlation_id if logger is not None else None,
            dry_run=dry_run,
        )
        if logger is not None:
            logger.emit(
                LogLevel.INFO,
                f"export {self.name_id} {status.value}",
                stage="export",
                connector=self.name_id,
                items=items,
                duration_ms=duration,
                destination=request.destination or "stdout",
                details={"format": request.fmt, "bytes": bytes_written},
            )
        return result

    def execute(
        self,
        request: ExportRequest,
        store: MemoryStore,
        *,
        graph_store: GraphStore | None = None,
        logger: StructuredLogger | None = None,
    ) -> ExportResult:
        """Render and write the export to its destination."""
        content, items = self._render(request, store, graph_store)
        return self._emit(request, content=content, items=items, dry_run=False, logger=logger)

    def dry_run(
        self,
        request: ExportRequest,
        store: MemoryStore,
        *,
        graph_store: GraphStore | None = None,
        logger: StructuredLogger | None = None,
    ) -> ExportResult:
        """Render the export without writing to the destination."""
        content, items = self._render(request, store, graph_store)
        return self._emit(request, content=content, items=items, dry_run=True, logger=logger)


class JsonExportConnector(_BaseExportConnector):
    """Export the organization report as JSON."""

    name_id = "json"
    formats = ("json",)
    summary = "Export the full organization intelligence report as JSON."

    def _render(
        self, request: ExportRequest, store: MemoryStore, graph_store: GraphStore | None
    ) -> tuple[str, int]:
        report = _report_from_store(store)
        return render_report(report, "json"), len(report.insights)


class MarkdownExportConnector(_BaseExportConnector):
    """Export the organization report as Markdown."""

    name_id = "markdown"
    formats = ("markdown", "md")
    summary = "Export the full organization intelligence report as Markdown."

    def _render(
        self, request: ExportRequest, store: MemoryStore, graph_store: GraphStore | None
    ) -> tuple[str, int]:
        report = _report_from_store(store)
        return render_report(report, "markdown"), len(report.insights)


class TextReportExportConnector(_BaseExportConnector):
    """Export the organization report as plain text."""

    name_id = "report"
    formats = ("text", "report")
    summary = "Export the full organization intelligence report as plain text."

    def _render(
        self, request: ExportRequest, store: MemoryStore, graph_store: GraphStore | None
    ) -> tuple[str, int]:
        report = _report_from_store(store)
        return render_report(report, "text"), len(report.insights)


class HtmlExportConnector(_BaseExportConnector):
    """Export the organization report as HTML."""

    name_id = "html"
    formats = ("html",)
    summary = "Export the full organization intelligence report as HTML."

    def _render(
        self, request: ExportRequest, store: MemoryStore, graph_store: GraphStore | None
    ) -> tuple[str, int]:
        report = _report_from_store(store)
        return report_to_html(report), len(report.insights)


class CsvExportConnector(_BaseExportConnector):
    """Export stored memories as CSV."""

    name_id = "csv"
    formats = ("csv",)
    summary = "Export stored memories as CSV rows."

    def _render(
        self, request: ExportRequest, store: MemoryStore, graph_store: GraphStore | None
    ) -> tuple[str, int]:
        return _memories_to_csv(store)


class GraphExportConnector(_BaseExportConnector):
    """Export the organizational knowledge graph (JSON, Mermaid, or DOT)."""

    name_id = "graph"
    formats = ("graph", "mermaid", "dot")
    summary = "Export the organizational knowledge graph as JSON, Mermaid, or DOT."

    def _render(
        self, request: ExportRequest, store: MemoryStore, graph_store: GraphStore | None
    ) -> tuple[str, int]:
        nodes, edges = _graph_data(store, graph_store)
        rendered = export_graph(nodes, edges, _GRAPH_FORMATS[request.fmt.lower()])
        if isinstance(rendered, dict):
            return json.dumps(rendered, indent=2, ensure_ascii=False), len(nodes)
        return rendered, len(nodes)


class MeetingSummaryExportConnector(_BaseExportConnector):
    """Export per-meeting markdown summaries."""

    name_id = "summary"
    formats = ("summary", "summaries")
    summary = "Export a markdown summary for every stored meeting."

    def _render(
        self, request: ExportRequest, store: MemoryStore, graph_store: GraphStore | None
    ) -> tuple[str, int]:
        return _meeting_summaries(store)


def register_all(registry: ConnectorRegistry) -> None:
    """Register every built-in export connector with ``registry``."""
    registry.register_export(JsonExportConnector())
    registry.register_export(MarkdownExportConnector())
    registry.register_export(TextReportExportConnector())
    registry.register_export(HtmlExportConnector())
    registry.register_export(CsvExportConnector())
    registry.register_export(GraphExportConnector())
    registry.register_export(MeetingSummaryExportConnector())
