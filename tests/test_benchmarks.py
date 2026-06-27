"""Tests for benchmark datasets and the performance benchmark runner (Phase 9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_memory.benchmarks import (
    DATASET_PRESETS,
    BenchmarkResult,
    BenchmarkRunner,
    DatasetSpec,
    generate_dataset,
    get_preset,
    run_benchmarks,
    write_dataset,
)
from meeting_memory.services import MeetingService


def test_presets_exist() -> None:
    assert set(DATASET_PRESETS) == {"small", "medium", "large", "enterprise"}


def test_get_preset_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_preset("gigantic")


def test_generate_dataset_is_deterministic() -> None:
    spec = get_preset("small")
    assert generate_dataset(spec) == generate_dataset(spec)


def test_dataset_richness() -> None:
    spec = get_preset("small")
    meetings = generate_dataset(spec)
    assert len(meetings) == spec.meetings
    # Multiple projects and cross-meeting references appear.
    assert len({meeting.project for meeting in meetings}) == spec.projects
    assert any("As decided in" in meeting.content for meeting in meetings)
    assert any("There is a risk that" in meeting.content for meeting in meetings)
    assert spec.estimated_utterances() == spec.meetings * spec.utterances_per_meeting


def test_pool_cycles_for_large_counts() -> None:
    spec = DatasetSpec(name="cycler", projects=20, people=20, meetings=4, utterances_per_meeting=10)
    meetings = generate_dataset(spec)
    assert len(meetings) == 4
    # Projects cycle through the (smaller) name pool without crashing.
    assert all(meeting.project for meeting in meetings)


def test_write_dataset_writes_files(tmp_path: Path) -> None:
    spec = get_preset("small")
    paths = write_dataset(spec, tmp_path / "out")
    assert len(paths) == spec.meetings
    assert all(path.exists() for path in paths)


def test_dataset_imports_all_memory_types(tmp_path: Path) -> None:
    spec = get_preset("small")
    write_dataset(spec, tmp_path / "data")
    db = tmp_path / "b.db"
    result = MeetingService(db).import_path(tmp_path / "data", recursive=True)
    assert result.meetings_imported == spec.meetings
    stats = MeetingService(db).stats()
    for memory_type in ("decision", "commitment", "risk", "assumption", "open_loop", "question"):
        assert stats.by_type[memory_type] > 0


def test_run_benchmarks_reports_every_operation() -> None:
    report = run_benchmarks(get_preset("small"), iterations=2)
    names = {result.name for result in report.results}
    assert {"import", "retrieval", "graph", "intelligence", "report_render"} <= names
    assert report.summary["meetings"] == 6
    assert report.summary["memories"] > 0
    assert int(report.summary["db_size_bytes"]) > 0  # type: ignore[call-overload]
    assert "import" in report.render_text()
    assert report.to_dict()["dataset"] == "small"


def test_report_result_lookup() -> None:
    report = run_benchmarks(get_preset("small"), iterations=1)
    assert report.result("import") is not None
    assert report.result("does-not-exist") is None


def test_runner_rejects_bad_iterations() -> None:
    with pytest.raises(ValueError, match="iterations"):
        BenchmarkRunner(get_preset("small"), iterations=0)


def test_benchmark_result_statistics() -> None:
    result = BenchmarkResult(name="x", unit="op", count=4, samples=(0.1, 0.2, 0.3, 0.4))
    assert result.total_seconds == pytest.approx(1.0)
    assert result.mean_ms == pytest.approx(250.0)
    assert result.median_ms == pytest.approx(250.0)
    assert result.min_ms == pytest.approx(100.0)
    assert result.max_ms == pytest.approx(400.0)
    assert result.throughput == pytest.approx(4.0)
    assert result.to_dict()["count"] == 4


def test_benchmark_result_handles_empty_samples() -> None:
    result = BenchmarkResult(name="empty", unit="op", count=0, samples=())
    assert result.mean_ms == 0.0
    assert result.median_ms == 0.0
    assert result.min_ms == 0.0
    assert result.max_ms == 0.0
    assert result.throughput == 0.0
