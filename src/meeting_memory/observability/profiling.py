"""Profiling utilities: CPU/memory profiling, timing, and slow-query detection.

These helpers wrap the standard-library :mod:`cProfile`, :mod:`pstats`, and
:mod:`tracemalloc` modules. Profiling output (which functions, which call counts,
which allocations) is deterministic for deterministic workloads; only the
measured durations vary, so callers should assert on structure rather than exact
timings. Every timing helper accepts an injectable ``clock`` for tests.
"""

from __future__ import annotations

import cProfile
import pstats
import time
import tracemalloc
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TypeVar, cast

T = TypeVar("T")


@dataclass(frozen=True)
class ProfileEntry:
    """A single function's contribution to a CPU profile."""

    function: str
    calls: int
    total_seconds: float
    cumulative_seconds: float

    def to_dict(self) -> dict[str, object]:
        """Serialise the entry into JSON-compatible primitives."""
        return {
            "function": self.function,
            "calls": self.calls,
            "total_seconds": round(self.total_seconds, 6),
            "cumulative_seconds": round(self.cumulative_seconds, 6),
        }


@dataclass(frozen=True)
class CPUProfile:
    """Top functions by cumulative time from a CPU profiling run."""

    entries: tuple[ProfileEntry, ...]
    total_seconds: float

    def to_dict(self) -> dict[str, object]:
        """Serialise the profile into JSON-compatible primitives."""
        return {
            "total_seconds": round(self.total_seconds, 6),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class MemoryAllocation:
    """A single source location's memory allocation."""

    location: str
    size_bytes: int
    count: int

    def to_dict(self) -> dict[str, object]:
        """Serialise the allocation into JSON-compatible primitives."""
        return {"location": self.location, "size_bytes": self.size_bytes, "count": self.count}


@dataclass(frozen=True)
class MemoryProfile:
    """Peak/current allocation plus the top allocating locations."""

    current_bytes: int
    peak_bytes: int
    top: tuple[MemoryAllocation, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialise the profile into JSON-compatible primitives."""
        return {
            "current_bytes": self.current_bytes,
            "peak_bytes": self.peak_bytes,
            "top": [allocation.to_dict() for allocation in self.top],
        }


def profile_cpu(
    func: Callable[..., T], *args: object, top: int = 10, **kwargs: object
) -> tuple[T, CPUProfile]:
    """Run ``func`` under :mod:`cProfile` and return its result and a profile."""
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        result = func(*args, **kwargs)
    finally:
        profiler.disable()

    stats = pstats.Stats(profiler)
    raw = cast("dict[tuple[str, int, str], tuple[int, int, float, float, object]]", stats.stats)  # type: ignore[attr-defined]
    entries: list[ProfileEntry] = []
    total = 0.0
    for (filename, lineno, name), (_, calls, total_time, cumulative_time, _callers) in raw.items():
        total += total_time
        entries.append(
            ProfileEntry(
                function=f"{filename}:{lineno}({name})",
                calls=calls,
                total_seconds=total_time,
                cumulative_seconds=cumulative_time,
            )
        )
    entries.sort(key=lambda entry: (-entry.cumulative_seconds, entry.function))
    return result, CPUProfile(entries=tuple(entries[:top]), total_seconds=total)


def profile_memory(
    func: Callable[..., T], *args: object, top: int = 10, **kwargs: object
) -> tuple[T, MemoryProfile]:
    """Run ``func`` under :mod:`tracemalloc` and return its result and a profile."""
    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    try:
        result = func(*args, **kwargs)
        snapshot = tracemalloc.take_snapshot()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        if not already_tracing:
            tracemalloc.stop()

    allocations: list[MemoryAllocation] = []
    for stat in snapshot.statistics("lineno")[:top]:
        frame = stat.traceback[0]
        allocations.append(
            MemoryAllocation(
                location=f"{frame.filename}:{frame.lineno}",
                size_bytes=stat.size,
                count=stat.count,
            )
        )
    return result, MemoryProfile(current_bytes=current, peak_bytes=peak, top=tuple(allocations))


@dataclass(frozen=True)
class StageTiming:
    """The measured duration of a single named pipeline stage."""

    name: str
    seconds: float

    def to_dict(self) -> dict[str, object]:
        """Serialise the stage into JSON-compatible primitives."""
        return {"name": self.name, "seconds": round(self.seconds, 6)}


@dataclass(frozen=True)
class PipelineTiming:
    """An ordered report of stage timings for a pipeline run."""

    stages: tuple[StageTiming, ...]

    @property
    def total_seconds(self) -> float:
        """Return the summed duration across all stages."""
        return sum(stage.seconds for stage in self.stages)

    def slowest(self) -> StageTiming | None:
        """Return the slowest stage, or ``None`` if there were none."""
        return max(self.stages, key=lambda stage: stage.seconds, default=None)

    def to_dict(self) -> dict[str, object]:
        """Serialise the timing report into JSON-compatible primitives."""
        slowest = self.slowest()
        return {
            "total_seconds": round(self.total_seconds, 6),
            "slowest": slowest.name if slowest is not None else None,
            "stages": [stage.to_dict() for stage in self.stages],
        }


class PipelineTimer:
    """Record the duration of sequential, named pipeline stages."""

    def __init__(self, *, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self._stages: list[StageTiming] = []

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Context manager that records the wrapped stage's duration."""
        start = self._clock()
        try:
            yield
        finally:
            self._stages.append(StageTiming(name=name, seconds=self._clock() - start))

    def measure(self, name: str, func: Callable[..., T], *args: object, **kwargs: object) -> T:
        """Run ``func`` as a named stage and return its result."""
        with self.stage(name):
            return func(*args, **kwargs)

    def result(self) -> PipelineTiming:
        """Return the collected timing report."""
        return PipelineTiming(stages=tuple(self._stages))


@dataclass(frozen=True)
class SlowQuery:
    """A measured operation that exceeded the slow-query threshold."""

    label: str
    seconds: float

    def to_dict(self) -> dict[str, object]:
        """Serialise the slow query into JSON-compatible primitives."""
        return {"label": self.label, "seconds": round(self.seconds, 6)}


class SlowQueryDetector:
    """Flag operations whose duration exceeds a threshold."""

    def __init__(
        self,
        threshold_seconds: float,
        *,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if threshold_seconds < 0:
            raise ValueError(f"threshold must be non-negative, got {threshold_seconds}")
        self.threshold_seconds = threshold_seconds
        self._clock = clock
        self._slow: list[SlowQuery] = []

    @contextmanager
    def measure(self, label: str) -> Iterator[None]:
        """Context manager that records ``label`` if it runs too slowly."""
        start = self._clock()
        try:
            yield
        finally:
            elapsed = self._clock() - start
            if elapsed >= self.threshold_seconds:
                self._slow.append(SlowQuery(label=label, seconds=elapsed))

    def run(self, label: str, func: Callable[..., T], *args: object, **kwargs: object) -> T:
        """Run ``func`` under measurement and return its result."""
        with self.measure(label):
            return func(*args, **kwargs)

    @property
    def slow_queries(self) -> tuple[SlowQuery, ...]:
        """Return every recorded slow query in observation order."""
        return tuple(self._slow)

    def to_dict(self) -> dict[str, object]:
        """Serialise detected slow queries into JSON-compatible primitives."""
        return {
            "threshold_seconds": self.threshold_seconds,
            "slow_queries": [query.to_dict() for query in self._slow],
        }


__all__ = [
    "CPUProfile",
    "MemoryAllocation",
    "MemoryProfile",
    "PipelineTimer",
    "PipelineTiming",
    "ProfileEntry",
    "SlowQuery",
    "SlowQueryDetector",
    "StageTiming",
    "profile_cpu",
    "profile_memory",
]
