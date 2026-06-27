"""Structured, machine-readable logging for the connector framework (Phase 7).

Logs are emitted as immutable :class:`LogRecord` value objects and written to a
pluggable sink (in-memory for tests, JSON Lines on disk for the CLI). Each record
carries the pipeline stage, connector, duration, item count, warning/error
counts, output destination, and a correlation id so a whole automation run can be
reconstructed deterministically.

Wall-clock concerns (elapsed time, timestamps) are injected via ``clock`` and
``now`` callables so runs can be made fully reproducible in tests.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class LogLevel(str, Enum):
    """Severity of a structured log record."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class LogRecord:
    """A single structured, machine-readable log entry."""

    correlation_id: str
    sequence: int
    level: LogLevel
    message: str
    stage: str | None = None
    connector: str | None = None
    items: int | None = None
    duration_ms: float | None = None
    destination: str | None = None
    warnings: int = 0
    errors: int = 0
    timestamp: str | None = None
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialise the record into JSON-compatible primitives."""
        return {
            "correlation_id": self.correlation_id,
            "sequence": self.sequence,
            "level": self.level.value,
            "message": self.message,
            "stage": self.stage,
            "connector": self.connector,
            "items": self.items,
            "duration_ms": (None if self.duration_ms is None else round(self.duration_ms, 3)),
            "destination": self.destination,
            "warnings": self.warnings,
            "errors": self.errors,
            "timestamp": self.timestamp,
            "details": dict(self.details),
        }


class LogSink:
    """Destination for structured log records."""

    def write(self, record: LogRecord) -> None:
        """Persist a single record."""
        raise NotImplementedError


class MemoryLogSink(LogSink):
    """Collect log records in memory (used by tests and in-process readers)."""

    def __init__(self) -> None:
        self._records: list[LogRecord] = []

    def write(self, record: LogRecord) -> None:
        """Append a record to the in-memory buffer."""
        self._records.append(record)

    @property
    def records(self) -> tuple[LogRecord, ...]:
        """Return the collected records in emission order."""
        return tuple(self._records)


class JsonlFileLogSink(LogSink):
    """Append structured records to a JSON Lines file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, record: LogRecord) -> None:
        """Append the record as a single JSON line, creating the file if needed."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def new_correlation_id() -> str:
    """Return a fresh, unique correlation id."""
    return uuid.uuid4().hex[:12]


class StructuredLogger:
    """Emit :class:`LogRecord` objects to a sink with monotonic sequencing."""

    def __init__(
        self,
        correlation_id: str | None = None,
        *,
        sink: LogSink | None = None,
        clock: Callable[[], float] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.correlation_id = correlation_id or new_correlation_id()
        self._sink = sink if sink is not None else MemoryLogSink()
        self._clock = clock
        self._now = now
        self._sequence = 0

    @property
    def sink(self) -> LogSink:
        """The sink records are written to."""
        return self._sink

    def elapsed(self, start: float) -> float:
        """Return milliseconds elapsed since ``start`` using the injected clock."""
        if self._clock is None:
            return 0.0
        return (self._clock() - start) * 1000.0

    def mark(self) -> float:
        """Return the current clock reading (0.0 when no clock is configured)."""
        return self._clock() if self._clock is not None else 0.0

    def _timestamp(self) -> str | None:
        if self._now is None:
            return None
        return self._now().isoformat()

    def emit(
        self,
        level: LogLevel,
        message: str,
        *,
        stage: str | None = None,
        connector: str | None = None,
        items: int | None = None,
        duration_ms: float | None = None,
        destination: str | None = None,
        warnings: int = 0,
        errors: int = 0,
        details: dict[str, object] | None = None,
    ) -> LogRecord:
        """Build, write, and return a single structured record."""
        self._sequence += 1
        record = LogRecord(
            correlation_id=self.correlation_id,
            sequence=self._sequence,
            level=level,
            message=message,
            stage=stage,
            connector=connector,
            items=items,
            duration_ms=duration_ms,
            destination=destination,
            warnings=warnings,
            errors=errors,
            timestamp=self._timestamp(),
            details=dict(details or {}),
        )
        self._sink.write(record)
        return record

    def records(self) -> tuple[LogRecord, ...]:
        """Return collected records when the sink keeps them in memory."""
        if isinstance(self._sink, MemoryLogSink):
            return self._sink.records
        return ()


def utc_now() -> datetime:
    """Return the current UTC time (default ``now`` provider for live runs)."""
    return datetime.now(timezone.utc)


def read_logs(
    path: str | Path,
    *,
    correlation_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    """Read structured log records back from a JSON Lines file.

    Returns the most recent ``limit`` records (after optional correlation-id
    filtering), preserving file order. A missing file yields an empty list.
    """
    file_path = Path(path)
    if not file_path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        record = json.loads(text)
        if correlation_id is not None and record.get("correlation_id") != correlation_id:
            continue
        records.append(record)
    if limit is not None and limit >= 0:
        records = records[-limit:]
    return records
