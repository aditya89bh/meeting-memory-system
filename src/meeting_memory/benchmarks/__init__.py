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

__all__ = [
    "DATASET_PRESETS",
    "DatasetSpec",
    "GeneratedMeeting",
    "generate_dataset",
    "get_preset",
    "write_dataset",
]
