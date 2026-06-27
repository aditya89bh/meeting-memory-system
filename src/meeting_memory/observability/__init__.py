"""Observability primitives (Phase 9).

A dependency-free metrics layer: counters, gauges, histograms, and timers
collected by a :class:`MetricsCollector`, plus :class:`HealthSnapshot` and
:class:`SystemMetrics`. Metrics export to JSON and to Prometheus text exposition
format without requiring the ``prometheus_client`` package. Profiling utilities
(CPU/memory profiling, hot-path timing, slow-query detection, pipeline timing)
live alongside in :mod:`meeting_memory.observability.profiling`.
"""

from __future__ import annotations

from .metrics import (
    Counter,
    Gauge,
    HealthCheck,
    HealthSnapshot,
    Histogram,
    MetricsCollector,
    SystemMetrics,
    Timer,
)
from .profiling import (
    CPUProfile,
    MemoryProfile,
    PipelineTimer,
    PipelineTiming,
    SlowQuery,
    SlowQueryDetector,
    profile_cpu,
    profile_memory,
)

__all__ = [
    "CPUProfile",
    "Counter",
    "Gauge",
    "HealthCheck",
    "HealthSnapshot",
    "Histogram",
    "MemoryProfile",
    "MetricsCollector",
    "PipelineTimer",
    "PipelineTiming",
    "SlowQuery",
    "SlowQueryDetector",
    "SystemMetrics",
    "Timer",
    "profile_cpu",
    "profile_memory",
]
