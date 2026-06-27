"""Benchmark datasets and performance benchmarking (Phase 9).

This package provides deterministic, reproducible benchmark datasets and a
benchmark runner that measures import throughput, retrieval latency, graph
construction, intelligence generation, and report rendering over them. Nothing
here adds user-facing features; it exists to validate performance, scalability,
and production readiness.
"""

from __future__ import annotations

from .datasets import (
    DATASET_PRESETS,
    DatasetSpec,
    GeneratedMeeting,
    generate_dataset,
    get_preset,
    write_dataset,
)
from .runner import (
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkRunner,
    run_benchmarks,
)
from .visualize import (
    Chart,
    bar_chart,
    comparison_charts,
    line_chart,
    report_charts,
    write_comparison_charts,
    write_report_charts,
)

__all__ = [
    "DATASET_PRESETS",
    "BenchmarkReport",
    "BenchmarkResult",
    "BenchmarkRunner",
    "Chart",
    "DatasetSpec",
    "GeneratedMeeting",
    "bar_chart",
    "comparison_charts",
    "generate_dataset",
    "get_preset",
    "line_chart",
    "report_charts",
    "run_benchmarks",
    "write_comparison_charts",
    "write_dataset",
    "write_report_charts",
]
