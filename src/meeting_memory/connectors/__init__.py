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

__all__ = [
    "AutomationConnector",
    "AutomationJob",
    "AutomationResult",
    "Connector",
    "ConnectorCapability",
    "ConnectorManager",
    "ConnectorMetadata",
    "ConnectorRegistry",
    "ConnectorResult",
    "ConnectorStatus",
    "ConnectorType",
    "ExecutionContext",
    "ExportConnector",
    "ExportRequest",
    "ExportResult",
    "FileImportOutcome",
    "ImportConnector",
    "ImportRequest",
    "ImportResult",
    "JsonlFileLogSink",
    "LogLevel",
    "LogRecord",
    "LogSink",
    "MemoryLogSink",
    "Schedule",
    "ScheduleFrequency",
    "StageResult",
    "StepConfig",
    "StructuredLogger",
    "new_correlation_id",
    "read_logs",
    "utc_now",
]
