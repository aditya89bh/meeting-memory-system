"""Connector framework and automation engine (Phase 7).

This package adds a deterministic, plugin-style framework for importing meeting
data from multiple sources and exporting organizational intelligence to multiple
destinations, plus an automation engine, scheduling primitives, structured
logging, and declarative pipeline configuration.

Everything builds on the existing pipeline (parser -> extraction -> storage ->
retrieval -> graph -> intelligence) and stays standard-library only: no external
schedulers, no network access, no credentials.
"""

from __future__ import annotations

from .base import (
    AutomationConnector,
    Connector,
    ConnectorManager,
    ConnectorRegistry,
    ExecutionContext,
    ExportConnector,
    ImportConnector,
    default_manager,
    default_registry,
)
from .exporters import (
    CsvExportConnector,
    GraphExportConnector,
    HtmlExportConnector,
    JsonExportConnector,
    MarkdownExportConnector,
    MeetingSummaryExportConnector,
    TextReportExportConnector,
    report_to_html,
)
from .importers import (
    ArchiveImportConnector,
    BatchImportConnector,
    CsvImportConnector,
    DirectoryImportConnector,
    JsonImportConnector,
    MarkdownImportConnector,
    RecursiveDirectoryImportConnector,
    TextImportConnector,
    csv_to_transcript,
    markdown_to_transcript,
)
from .logging import (
    JsonlFileLogSink,
    LogLevel,
    LogRecord,
    LogSink,
    MemoryLogSink,
    StructuredLogger,
    new_correlation_id,
    read_logs,
    utc_now,
)
from .models import (
    AutomationJob,
    AutomationResult,
    ConnectorCapability,
    ConnectorMetadata,
    ConnectorResult,
    ConnectorStatus,
    ConnectorType,
    ExportRequest,
    ExportResult,
    FileImportOutcome,
    ImportRequest,
    ImportResult,
    Schedule,
    ScheduleFrequency,
    StageResult,
    StepConfig,
)
from .scheduler import (
    CronSpec,
    Scheduler,
    cron_next,
    next_run,
    parse_cron,
    simulate,
)

__all__ = [
    "ArchiveImportConnector",
    "AutomationConnector",
    "AutomationJob",
    "AutomationResult",
    "BatchImportConnector",
    "Connector",
    "ConnectorCapability",
    "ConnectorManager",
    "ConnectorMetadata",
    "ConnectorRegistry",
    "ConnectorResult",
    "ConnectorStatus",
    "ConnectorType",
    "CronSpec",
    "CsvExportConnector",
    "CsvImportConnector",
    "DirectoryImportConnector",
    "ExecutionContext",
    "ExportConnector",
    "ExportRequest",
    "ExportResult",
    "FileImportOutcome",
    "GraphExportConnector",
    "HtmlExportConnector",
    "ImportConnector",
    "ImportRequest",
    "ImportResult",
    "JsonExportConnector",
    "JsonImportConnector",
    "JsonlFileLogSink",
    "LogLevel",
    "LogRecord",
    "LogSink",
    "MarkdownExportConnector",
    "MarkdownImportConnector",
    "MeetingSummaryExportConnector",
    "MemoryLogSink",
    "RecursiveDirectoryImportConnector",
    "Schedule",
    "ScheduleFrequency",
    "Scheduler",
    "StageResult",
    "StepConfig",
    "StructuredLogger",
    "TextImportConnector",
    "TextReportExportConnector",
    "cron_next",
    "csv_to_transcript",
    "default_manager",
    "default_registry",
    "markdown_to_transcript",
    "new_correlation_id",
    "next_run",
    "parse_cron",
    "read_logs",
    "report_to_html",
    "simulate",
    "utc_now",
]
