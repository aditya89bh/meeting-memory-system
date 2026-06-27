"""Tests for structured logging."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from connector_helpers import fake_clock
from meeting_memory.connectors import (
    JsonlFileLogSink,
    LogLevel,
    MemoryLogSink,
    StructuredLogger,
    new_correlation_id,
    read_logs,
)
from meeting_memory.connectors.logging import LogRecord, utc_now


def test_log_record_to_dict_rounds_duration() -> None:
    record = LogRecord(
        correlation_id="cid",
        sequence=1,
        level=LogLevel.INFO,
        message="hi",
        duration_ms=1.23456,
    )
    payload = record.to_dict()
    assert payload["duration_ms"] == 1.235
    assert payload["level"] == "info"


def test_memory_sink_collects_in_order() -> None:
    logger = StructuredLogger("cid", clock=fake_clock())
    logger.emit(LogLevel.INFO, "first", stage="a")
    logger.emit(LogLevel.WARNING, "second", stage="b", warnings=1)
    records = logger.records()
    assert [r.sequence for r in records] == [1, 2]
    assert records[1].level is LogLevel.WARNING


def test_elapsed_and_mark_with_clock() -> None:
    logger = StructuredLogger("cid", clock=fake_clock())
    start = logger.mark()
    elapsed = logger.elapsed(start)
    assert elapsed >= 0.0


def test_no_clock_defaults_to_zero() -> None:
    logger = StructuredLogger("cid")
    assert logger.mark() == 0.0
    assert logger.elapsed(0.0) == 0.0
    assert logger.records() == ()


def test_timestamp_provider() -> None:
    fixed = datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc)
    logger = StructuredLogger("cid", now=lambda: fixed)
    record = logger.emit(LogLevel.INFO, "hi")
    assert record.timestamp == fixed.isoformat()


def test_jsonl_sink_and_read_logs(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "run.jsonl"
    logger = StructuredLogger("cid-1", sink=JsonlFileLogSink(path))
    logger.emit(LogLevel.INFO, "one", stage="import", connector="text")
    other = StructuredLogger("cid-2", sink=JsonlFileLogSink(path))
    other.emit(LogLevel.ERROR, "two", stage="export")

    everything = read_logs(path)
    assert len(everything) == 2
    filtered = read_logs(path, correlation_id="cid-1")
    assert len(filtered) == 1
    assert filtered[0]["message"] == "one"
    limited = read_logs(path, limit=1)
    assert len(limited) == 1
    assert limited[0]["message"] == "two"


def test_read_logs_missing_file(tmp_path: Path) -> None:
    assert read_logs(tmp_path / "absent.jsonl") == []


def test_sink_property_and_helpers() -> None:
    sink = MemoryLogSink()
    logger = StructuredLogger("cid", sink=sink)
    assert logger.sink is sink
    assert new_correlation_id() != new_correlation_id()
    assert utc_now().tzinfo is timezone.utc
