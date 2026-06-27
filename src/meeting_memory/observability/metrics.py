"""Dependency-free metrics, health, and system snapshots."""

from __future__ import annotations

import json
import platform as platform_module
import resource
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

_DEFAULT_BUCKETS: tuple[float, ...] = (
    0.001,
    0.005,
    0.01,
    0.05,
    0.1,
    0.5,
    1.0,
    5.0,
)


class Counter:
    """A monotonically increasing counter."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._value = 0.0

    def inc(self, amount: float = 1.0) -> None:
        """Increment the counter by ``amount`` (must be non-negative)."""
        if amount < 0:
            raise ValueError(f"counter {self.name!r} cannot decrease (amount={amount})")
        self._value += amount

    @property
    def value(self) -> float:
        """Return the current counter value."""
        return self._value

    def reset(self) -> None:
        """Reset the counter to zero."""
        self._value = 0.0


class Gauge:
    """A point-in-time value that can go up or down."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._value = 0.0

    def set(self, value: float) -> None:
        """Set the gauge to ``value``."""
        self._value = value

    def inc(self, amount: float = 1.0) -> None:
        """Increment the gauge by ``amount``."""
        self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        """Decrement the gauge by ``amount``."""
        self._value -= amount

    @property
    def value(self) -> float:
        """Return the current gauge value."""
        return self._value


class Histogram:
    """Records observations and exposes summary statistics and buckets."""

    def __init__(self, name: str, *, buckets: tuple[float, ...] = _DEFAULT_BUCKETS) -> None:
        self.name = name
        self.buckets = tuple(sorted(buckets))
        self._samples: list[float] = []

    def observe(self, value: float) -> None:
        """Record a single observation."""
        self._samples.append(value)

    @property
    def count(self) -> int:
        """Return the number of recorded observations."""
        return len(self._samples)

    @property
    def sum(self) -> float:
        """Return the sum of all observations."""
        return sum(self._samples)

    @property
    def mean(self) -> float:
        """Return the mean observation (0.0 when empty)."""
        return self.sum / len(self._samples) if self._samples else 0.0

    @property
    def min(self) -> float:
        """Return the smallest observation (0.0 when empty)."""
        return min(self._samples) if self._samples else 0.0

    @property
    def max(self) -> float:
        """Return the largest observation (0.0 when empty)."""
        return max(self._samples) if self._samples else 0.0

    def percentile(self, quantile: float) -> float:
        """Return the value at ``quantile`` (0..1) using nearest-rank."""
        if not 0.0 <= quantile <= 1.0:
            raise ValueError(f"quantile must be in [0, 1], got {quantile}")
        if not self._samples:
            return 0.0
        ordered = sorted(self._samples)
        rank = max(1, round(quantile * len(ordered)))
        return ordered[min(rank, len(ordered)) - 1]

    def bucket_counts(self) -> dict[str, int]:
        """Return cumulative ``le`` bucket counts (including ``+Inf``)."""
        counts: dict[str, int] = {}
        for edge in self.buckets:
            counts[_format_float(edge)] = sum(1 for value in self._samples if value <= edge)
        counts["+Inf"] = len(self._samples)
        return counts

    def snapshot(self) -> dict[str, object]:
        """Return summary statistics as JSON-compatible primitives."""
        return {
            "count": self.count,
            "sum": self.sum,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "p50": self.percentile(0.5),
            "p95": self.percentile(0.95),
            "p99": self.percentile(0.99),
            "buckets": self.bucket_counts(),
        }

    def reset(self) -> None:
        """Discard all recorded observations."""
        self._samples.clear()


class Timer:
    """A histogram specialised for timing durations (in seconds)."""

    def __init__(self, name: str, *, clock: Callable[[], float] = time.perf_counter) -> None:
        self.name = name
        self.histogram = Histogram(name)
        self._clock = clock

    def record(self, seconds: float) -> None:
        """Record a duration in seconds."""
        self.histogram.observe(seconds)

    @contextmanager
    def time(self) -> Iterator[None]:
        """Context manager that records the wrapped block's duration."""
        start = self._clock()
        try:
            yield
        finally:
            self.record(self._clock() - start)

    def snapshot(self) -> dict[str, object]:
        """Return the underlying histogram snapshot."""
        return self.histogram.snapshot()


class MetricsCollector:
    """A thread-safe registry of counters, gauges, histograms, and timers."""

    def __init__(self, *, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._timers: dict[str, Timer] = {}

    def counter(self, name: str) -> Counter:
        """Return (creating if needed) the named counter."""
        with self._lock:
            return self._counters.setdefault(name, Counter(name))

    def gauge(self, name: str) -> Gauge:
        """Return (creating if needed) the named gauge."""
        with self._lock:
            return self._gauges.setdefault(name, Gauge(name))

    def histogram(self, name: str) -> Histogram:
        """Return (creating if needed) the named histogram."""
        with self._lock:
            return self._histograms.setdefault(name, Histogram(name))

    def timer(self, name: str) -> Timer:
        """Return (creating if needed) the named timer."""
        with self._lock:
            return self._timers.setdefault(name, Timer(name, clock=self._clock))

    def snapshot(self) -> dict[str, object]:
        """Return a JSON-compatible snapshot of every registered metric."""
        with self._lock:
            return {
                "counters": {name: counter.value for name, counter in self._counters.items()},
                "gauges": {name: gauge.value for name, gauge in self._gauges.items()},
                "histograms": {
                    name: histogram.snapshot() for name, histogram in self._histograms.items()
                },
                "timers": {name: timer.snapshot() for name, timer in self._timers.items()},
            }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise the snapshot to JSON."""
        return json.dumps(self.snapshot(), indent=indent, sort_keys=True)

    def to_prometheus(self) -> str:
        """Render every metric in Prometheus text exposition format."""
        with self._lock:
            lines: list[str] = []
            for name, counter in sorted(self._counters.items()):
                metric = _sanitize(name)
                lines.append(f"# TYPE {metric} counter")
                lines.append(f"{metric} {_format_float(counter.value)}")
            for name, gauge in sorted(self._gauges.items()):
                metric = _sanitize(name)
                lines.append(f"# TYPE {metric} gauge")
                lines.append(f"{metric} {_format_float(gauge.value)}")
            for name, histogram in sorted(self._histograms.items()):
                lines.extend(_prometheus_histogram(_sanitize(name), histogram))
            for name, timer in sorted(self._timers.items()):
                lines.extend(_prometheus_histogram(f"{_sanitize(name)}_seconds", timer.histogram))
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Clear every registered metric."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()


@dataclass(frozen=True)
class HealthCheck:
    """The result of a single named health check."""

    name: str
    healthy: bool
    detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialise the check into JSON-compatible primitives."""
        return {"name": self.name, "healthy": self.healthy, "detail": self.detail}


@dataclass(frozen=True)
class HealthSnapshot:
    """An aggregate health status across several checks."""

    status: str
    checks: tuple[HealthCheck, ...]
    timestamp: str

    @classmethod
    def build(
        cls, checks: tuple[HealthCheck, ...], *, now: datetime | None = None
    ) -> HealthSnapshot:
        """Build a snapshot, deriving ``status`` from the checks."""
        moment = now or datetime.now(timezone.utc)
        status = "ok" if all(check.healthy for check in checks) else "degraded"
        return cls(status=status, checks=checks, timestamp=moment.isoformat())

    @property
    def healthy(self) -> bool:
        """Return whether every check passed."""
        return self.status == "ok"

    def to_dict(self) -> dict[str, object]:
        """Serialise the snapshot into JSON-compatible primitives."""
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class SystemMetrics:
    """A point-in-time snapshot of process and runtime resource usage."""

    max_rss_bytes: int
    user_cpu_seconds: float
    system_cpu_seconds: float
    thread_count: int
    python_version: str
    platform: str = field(default_factory=platform_module.platform)

    @classmethod
    def capture(cls) -> SystemMetrics:
        """Capture current process resource usage via the standard library."""
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ``ru_maxrss`` is bytes on macOS and kibibytes on Linux.
        max_rss = usage.ru_maxrss
        if not sys.platform.startswith("darwin"):
            max_rss *= 1024
        return cls(
            max_rss_bytes=int(max_rss),
            user_cpu_seconds=float(usage.ru_utime),
            system_cpu_seconds=float(usage.ru_stime),
            thread_count=threading.active_count(),
            python_version=platform_module.python_version(),
            platform=platform_module.platform(),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialise the metrics into JSON-compatible primitives."""
        return {
            "max_rss_bytes": self.max_rss_bytes,
            "user_cpu_seconds": self.user_cpu_seconds,
            "system_cpu_seconds": self.system_cpu_seconds,
            "thread_count": self.thread_count,
            "python_version": self.python_version,
            "platform": self.platform,
        }


def _format_float(value: float) -> str:
    """Format a float for Prometheus output without trailing noise."""
    if value == int(value):
        return str(int(value))
    return repr(value)


def _sanitize(name: str) -> str:
    """Sanitise a metric name into a valid Prometheus identifier."""
    cleaned = "".join(char if char.isalnum() or char == "_" else "_" for char in name)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned or "metric"


def _prometheus_histogram(metric: str, histogram: Histogram) -> list[str]:
    """Render a histogram in Prometheus text format."""
    lines = [f"# TYPE {metric} histogram"]
    for edge, count in histogram.bucket_counts().items():
        lines.append(f'{metric}_bucket{{le="{edge}"}} {count}')
    lines.append(f"{metric}_sum {_format_float(histogram.sum)}")
    lines.append(f"{metric}_count {histogram.count}")
    return lines
