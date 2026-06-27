"""Tests for the dependency-free benchmark SVG visualizations (Phase 10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_memory.benchmarks import (
    BenchmarkReport,
    BenchmarkResult,
    bar_chart,
    comparison_charts,
    line_chart,
    report_charts,
    write_comparison_charts,
    write_report_charts,
)


def _report(name: str, *, memories: int, db_bytes: int, peak: int) -> BenchmarkReport:
    return BenchmarkReport(
        dataset=name,
        iterations=1,
        results=(
            BenchmarkResult(name="import", unit="meeting", count=6, samples=(0.02,)),
            BenchmarkResult(name="retrieval", unit="query", count=3, samples=(0.001, 0.002)),
            BenchmarkResult(name="graph", unit="build", count=1, samples=(0.005,)),
            BenchmarkResult(name="intelligence", unit="report", count=1, samples=(0.01,)),
        ),
        summary={
            "meetings": 6,
            "memories": memories,
            "db_size_bytes": db_bytes,
            "peak_memory_bytes": peak,
        },
    )


def test_bar_chart_structure() -> None:
    svg = bar_chart("Title", ["a", "b"], [1.0, 2.0], y_label="units")
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "Title" in svg
    assert svg.count("<rect") >= 3  # background + 2 bars
    assert "units" in svg


def test_bar_chart_handles_all_zero_values() -> None:
    svg = bar_chart("Zero", ["x"], [0.0], y_label="u")
    assert "<svg" in svg


def test_bar_chart_length_mismatch() -> None:
    with pytest.raises(ValueError):
        bar_chart("bad", ["a"], [1.0, 2.0], y_label="u")


def test_line_chart_structure() -> None:
    svg = line_chart("Growth", [1.0, 2.0, 3.0], [10.0, 20.0, 30.0], x_label="x", y_label="y")
    assert "<path" in svg
    assert svg.count("<circle") == 3
    assert "Growth" in svg


def test_line_chart_single_point_has_no_path() -> None:
    svg = line_chart("One", [1.0], [5.0], x_label="x", y_label="y")
    assert "<path" not in svg
    assert svg.count("<circle") == 1


def test_line_chart_length_mismatch() -> None:
    with pytest.raises(ValueError):
        line_chart("bad", [1.0], [1.0, 2.0], x_label="x", y_label="y")


def test_comparison_charts_cover_all_metrics() -> None:
    reports = [
        _report("small", memories=80, db_bytes=40000, peak=1_000_000),
        _report("large", memories=800, db_bytes=400000, peak=8_000_000),
    ]
    charts = comparison_charts(reports)
    names = {chart.filename for chart in charts}
    assert names == {
        "import_throughput.svg",
        "retrieval_latency.svg",
        "graph_generation.svg",
        "intelligence_generation.svg",
        "memory_usage.svg",
        "database_growth.svg",
    }
    for chart in charts:
        assert chart.svg.startswith("<svg")


def test_comparison_charts_requires_reports() -> None:
    with pytest.raises(ValueError):
        comparison_charts([])


def test_report_charts() -> None:
    charts = report_charts(_report("small", memories=80, db_bytes=40000, peak=1_000_000))
    assert {c.filename for c in charts} == {"operation_latency.svg", "operation_throughput.svg"}


def test_write_helpers(tmp_path: Path) -> None:
    reports = [_report("small", memories=80, db_bytes=40000, peak=1_000_000)]
    paths = write_comparison_charts(reports, tmp_path / "cmp")
    assert len(paths) == 6
    assert all(p.exists() and p.read_text().startswith("<svg") for p in paths)

    rpaths = write_report_charts(reports[0], tmp_path / "single")
    assert len(rpaths) == 2
    assert all(p.exists() for p in rpaths)


def test_missing_result_defaults_to_zero(tmp_path: Path) -> None:
    sparse = BenchmarkReport(dataset="x", iterations=1, results=(), summary={})
    charts = comparison_charts([sparse])
    assert len(charts) == 6


def test_cli_benchmark_charts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from meeting_memory.cli import main

    out = tmp_path / "charts"
    assert main(["benchmark", "--dataset", "small", "--charts", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "chart:" in printed
    assert (out / "operation_latency.svg").exists()
    assert (out / "operation_throughput.svg").exists()
