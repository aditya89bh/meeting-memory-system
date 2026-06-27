"""Tests for the deterministic export connectors."""

from __future__ import annotations

import json
from pathlib import Path

from connector_helpers import fake_clock, populate_store, write_transcripts
from meeting_memory.connectors import (
    ConnectorStatus,
    ExportRequest,
    StructuredLogger,
    default_manager,
    report_to_html,
)
from meeting_memory.connectors.exporters import (
    CsvExportConnector,
    GraphExportConnector,
    HtmlExportConnector,
    JsonExportConnector,
    MarkdownExportConnector,
    MeetingSummaryExportConnector,
    TextReportExportConnector,
)
from meeting_memory.intelligence import IntelligenceEngine
from meeting_memory.storage import SQLiteMemoryStore


def _seeded(tmp_path: Path) -> SQLiteMemoryStore:
    store = SQLiteMemoryStore(":memory:")
    populate_store(store, write_transcripts(tmp_path / "data"))
    return store


def test_json_export(tmp_path: Path) -> None:
    with _seeded(tmp_path) as store:
        result = JsonExportConnector().execute(ExportRequest(fmt="json"), store)
    assert result.status is ConnectorStatus.SUCCESS
    json.loads(result.content or "")


def test_markdown_and_text_reports(tmp_path: Path) -> None:
    with _seeded(tmp_path) as store:
        md = MarkdownExportConnector().execute(ExportRequest(fmt="markdown"), store)
        text = TextReportExportConnector().execute(ExportRequest(fmt="text"), store)
    assert (md.content or "").startswith("# Organizational Intelligence Report")
    assert "ORGANIZATIONAL INTELLIGENCE REPORT" in (text.content or "")


def test_html_export_is_valid_document(tmp_path: Path) -> None:
    with _seeded(tmp_path) as store:
        result = HtmlExportConnector().execute(ExportRequest(fmt="html"), store)
    content = result.content or ""
    assert content.startswith("<!DOCTYPE html>")
    assert "</html>" in content


def test_csv_export_has_header(tmp_path: Path) -> None:
    with _seeded(tmp_path) as store:
        result = CsvExportConnector().execute(ExportRequest(fmt="csv"), store)
    assert (result.content or "").splitlines()[0].startswith("memory_id,meeting_id")
    assert result.items_exported > 0


def test_graph_export_formats(tmp_path: Path) -> None:
    with _seeded(tmp_path) as store:
        as_json = GraphExportConnector().execute(ExportRequest(fmt="graph"), store)
        as_mermaid = GraphExportConnector().execute(ExportRequest(fmt="mermaid"), store)
        as_dot = GraphExportConnector().execute(ExportRequest(fmt="dot"), store)
    json.loads(as_json.content or "")
    assert (as_mermaid.content or "").startswith("graph TD")
    assert (as_dot.content or "").startswith("digraph")


def test_graph_export_uses_provided_graph_store(tmp_path: Path) -> None:
    from meeting_memory.graph import SQLiteGraphStore, build_graph

    with _seeded(tmp_path) as store:
        graph = SQLiteGraphStore(":memory:")
        build_graph(store, graph)
        try:
            result = GraphExportConnector().execute(
                ExportRequest(fmt="graph"), store, graph_store=graph
            )
        finally:
            graph.close()
    assert result.items_exported > 0


def test_summary_export(tmp_path: Path) -> None:
    with _seeded(tmp_path) as store:
        result = MeetingSummaryExportConnector().execute(ExportRequest(fmt="summary"), store)
    assert (result.content or "").startswith("# Meeting summaries")
    assert result.items_exported == 4


def test_export_writes_file(tmp_path: Path) -> None:
    destination = tmp_path / "out" / "report.md"
    logger = StructuredLogger("cid", clock=fake_clock())
    with _seeded(tmp_path) as store:
        result = MarkdownExportConnector().execute(
            ExportRequest(fmt="markdown", destination=str(destination)), store, logger=logger
        )
    assert destination.exists()
    assert result.bytes_written > 0
    assert destination.read_text(encoding="utf-8").endswith("\n")
    assert logger.records()


def test_export_dry_run_skips_write(tmp_path: Path) -> None:
    destination = tmp_path / "report.md"
    with _seeded(tmp_path) as store:
        result = MarkdownExportConnector().dry_run(
            ExportRequest(fmt="markdown", destination=str(destination), dry_run=True), store
        )
    assert result.status is ConnectorStatus.DRY_RUN
    assert not destination.exists()
    assert result.bytes_written == 0


def test_export_validation(tmp_path: Path) -> None:
    connector = MarkdownExportConnector()
    assert connector.validate(ExportRequest(fmt="markdown")) == []
    bad_fmt = connector.validate(ExportRequest(fmt="json"))
    assert any("does not support" in problem for problem in bad_fmt)
    bad_dest = connector.validate(
        ExportRequest(fmt="markdown", destination=str(tmp_path / "missing" / "out.md"))
    )
    assert any("destination directory does not exist" in problem for problem in bad_dest)


def test_manager_export(tmp_path: Path) -> None:
    manager = default_manager()
    with _seeded(tmp_path) as store:
        result = manager.export(ExportRequest(fmt="markdown"), store)
    assert result.status is ConnectorStatus.SUCCESS


def test_report_to_html_handles_empty_store() -> None:
    with SQLiteMemoryStore(":memory:") as store:
        report = IntelligenceEngine().analyze(store)
    html = report_to_html(report)
    assert "<h2>Recommendations</h2>" in html
    assert "<p>None</p>" in html
