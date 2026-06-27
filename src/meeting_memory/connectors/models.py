"""Typed models for the connector framework and automation engine (Phase 7).

Every model is an immutable, JSON-serialisable value object. Connectors describe
themselves with :class:`ConnectorMetadata`, accept typed requests
(:class:`ImportRequest`/:class:`ExportRequest`), and return typed results
(:class:`ImportResult`/:class:`ExportResult`). Automation jobs are declarative
(:class:`AutomationJob` + :class:`StepConfig` + :class:`Schedule`) and produce a
deterministic :class:`AutomationResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ConnectorType(str, Enum):
    """The role a connector plays in the framework."""

    IMPORT = "import"
    EXPORT = "export"
    AUTOMATION = "automation"

    def __str__(self) -> str:
        return self.value


class ConnectorStatus(str, Enum):
    """The outcome of a connector or automation run."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"

    def __str__(self) -> str:
        return self.value


class ConnectorCapability(str, Enum):
    """A discrete capability a connector advertises."""

    DRY_RUN = "dry_run"
    VALIDATION = "validation"
    RECURSIVE = "recursive"
    BATCH = "batch"
    DIRECTORY = "directory"
    ARCHIVE = "archive"
    STREAMING = "streaming"

    def __str__(self) -> str:
        return self.value


class ScheduleFrequency(str, Enum):
    """How often an automation job should run."""

    ONCE = "once"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"
    CRON = "cron"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ConnectorMetadata:
    """Self-description of a connector, used for discovery and validation."""

    name: str
    version: str
    connector_type: ConnectorType
    description: str = ""
    capabilities: frozenset[ConnectorCapability] = frozenset()
    formats: tuple[str, ...] = ()

    def supports(self, capability: ConnectorCapability) -> bool:
        """Return whether this connector advertises ``capability``."""
        return capability in self.capabilities

    def to_dict(self) -> dict[str, object]:
        """Serialise the metadata into JSON-compatible primitives."""
        return {
            "name": self.name,
            "version": self.version,
            "connector_type": self.connector_type.value,
            "description": self.description,
            "capabilities": sorted(cap.value for cap in self.capabilities),
            "formats": list(self.formats),
        }


@dataclass(frozen=True)
class ConnectorResult:
    """A generic, uniform result envelope for any connector invocation."""

    connector: str
    status: ConnectorStatus
    items_processed: int = 0
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    duration_ms: float = 0.0
    correlation_id: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether the run completed without a hard failure."""
        return self.status is not ConnectorStatus.FAILURE

    def to_dict(self) -> dict[str, object]:
        """Serialise the result into JSON-compatible primitives."""
        return {
            "connector": self.connector,
            "status": self.status.value,
            "items_processed": self.items_processed,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration_ms": round(self.duration_ms, 3),
            "correlation_id": self.correlation_id,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ImportRequest:
    """A deterministic request to import meeting data from a source."""

    source: str
    sources: tuple[str, ...] = ()
    recursive: bool = False
    pattern: str = "*"
    deduplicate: bool = True
    dry_run: bool = False
    now: str | None = None
    min_confidence: float = 0.0
    memory_types: frozenset[str] = frozenset()
    limit: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the import request into JSON-compatible primitives."""
        return {
            "source": self.source,
            "sources": list(self.sources),
            "recursive": self.recursive,
            "pattern": self.pattern,
            "deduplicate": self.deduplicate,
            "dry_run": self.dry_run,
            "now": self.now,
            "min_confidence": self.min_confidence,
            "memory_types": sorted(self.memory_types),
            "limit": self.limit,
        }


@dataclass(frozen=True)
class FileImportOutcome:
    """The outcome of importing a single file within an import run."""

    path: str
    status: ConnectorStatus
    meeting_id: str | None = None
    stored: int = 0
    duplicate: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the per-file outcome into JSON-compatible primitives."""
        return {
            "path": self.path,
            "status": self.status.value,
            "meeting_id": self.meeting_id,
            "stored": self.stored,
            "duplicate": self.duplicate,
            "error": self.error,
        }


@dataclass(frozen=True)
class ImportResult:
    """Aggregate result of an import connector run."""

    connector: str
    status: ConnectorStatus
    files_processed: int = 0
    meetings_imported: int = 0
    memories_stored: int = 0
    duplicates: int = 0
    outcomes: tuple[FileImportOutcome, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    duration_ms: float = 0.0
    correlation_id: str | None = None
    dry_run: bool = False

    def summary_lines(self) -> list[str]:
        """Human-readable summary lines for CLI output."""
        prefix = "[dry-run] " if self.dry_run else ""
        lines = [
            f"{prefix}{self.connector}: {self.status.value}",
            f"{self.files_processed} files processed",
            f"{self.meetings_imported} meetings imported",
            f"{self.memories_stored} memories stored",
        ]
        if self.duplicates:
            lines.append(f"{self.duplicates} duplicate files skipped")
        for warning in self.warnings:
            lines.append(f"warning: {warning}")
        for error in self.errors:
            lines.append(f"error: {error}")
        return lines

    def to_dict(self) -> dict[str, object]:
        """Serialise the import result into JSON-compatible primitives."""
        return {
            "connector": self.connector,
            "status": self.status.value,
            "files_processed": self.files_processed,
            "meetings_imported": self.meetings_imported,
            "memories_stored": self.memories_stored,
            "duplicates": self.duplicates,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration_ms": round(self.duration_ms, 3),
            "correlation_id": self.correlation_id,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class ExportRequest:
    """A deterministic request to export organizational data to a destination."""

    fmt: str
    destination: str | None = None
    dry_run: bool = False
    options: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialise the export request into JSON-compatible primitives."""
        return {
            "fmt": self.fmt,
            "destination": self.destination,
            "dry_run": self.dry_run,
            "options": dict(self.options),
        }


@dataclass(frozen=True)
class ExportResult:
    """Result of an export connector run."""

    connector: str
    status: ConnectorStatus
    fmt: str
    destination: str | None = None
    items_exported: int = 0
    bytes_written: int = 0
    content: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    duration_ms: float = 0.0
    correlation_id: str | None = None
    dry_run: bool = False

    def summary_lines(self) -> list[str]:
        """Human-readable summary lines for CLI output."""
        prefix = "[dry-run] " if self.dry_run else ""
        target = self.destination or "stdout"
        lines = [
            f"{prefix}{self.connector}: {self.status.value}",
            f"format: {self.fmt}",
            f"destination: {target}",
            f"{self.items_exported} items exported",
        ]
        if self.bytes_written:
            lines.append(f"{self.bytes_written} bytes written")
        for warning in self.warnings:
            lines.append(f"warning: {warning}")
        for error in self.errors:
            lines.append(f"error: {error}")
        return lines

    def to_dict(self) -> dict[str, object]:
        """Serialise the export result into JSON-compatible primitives."""
        return {
            "connector": self.connector,
            "status": self.status.value,
            "fmt": self.fmt,
            "destination": self.destination,
            "items_exported": self.items_exported,
            "bytes_written": self.bytes_written,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration_ms": round(self.duration_ms, 3),
            "correlation_id": self.correlation_id,
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class Schedule:
    """A deterministic schedule definition for an automation job."""

    frequency: ScheduleFrequency = ScheduleFrequency.MANUAL
    expression: str | None = None
    at: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the schedule into JSON-compatible primitives."""
        return {
            "frequency": self.frequency.value,
            "expression": self.expression,
            "at": self.at,
        }


@dataclass(frozen=True)
class StepConfig:
    """A single declarative step within an automation pipeline."""

    type: str
    params: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialise the step config into JSON-compatible primitives."""
        return {"type": self.type, "params": dict(self.params)}


@dataclass(frozen=True)
class AutomationJob:
    """A declarative automation job: an ordered pipeline plus a schedule."""

    name: str
    steps: tuple[StepConfig, ...] = ()
    schedule: Schedule = field(default_factory=Schedule)
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        """Serialise the job into JSON-compatible primitives."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "schedule": self.schedule.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class StageResult:
    """The result of executing one pipeline stage."""

    stage: str
    status: ConnectorStatus
    connector: str | None = None
    items: int = 0
    duration_ms: float = 0.0
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialise the stage result into JSON-compatible primitives."""
        return {
            "stage": self.stage,
            "status": self.status.value,
            "connector": self.connector,
            "items": self.items,
            "duration_ms": round(self.duration_ms, 3),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class AutomationResult:
    """Deterministic result of running an automation job end to end."""

    job: str
    correlation_id: str
    status: ConnectorStatus
    started_at: str
    finished_at: str
    duration_ms: float = 0.0
    stages: tuple[StageResult, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    dry_run: bool = False

    def summary_lines(self) -> list[str]:
        """Human-readable summary lines for CLI output."""
        prefix = "[dry-run] " if self.dry_run else ""
        lines = [
            f"{prefix}job {self.job}: {self.status.value}",
            f"correlation: {self.correlation_id}",
            f"stages: {len(self.stages)}",
        ]
        for stage in self.stages:
            lines.append(f"  - {stage.stage} [{stage.status.value}] ({stage.items} items)")
        for error in self.errors:
            lines.append(f"error: {error}")
        return lines

    def to_dict(self) -> dict[str, object]:
        """Serialise the automation result into JSON-compatible primitives."""
        return {
            "job": self.job,
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 3),
            "stages": [stage.to_dict() for stage in self.stages],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "dry_run": self.dry_run,
        }
