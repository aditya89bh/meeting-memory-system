"""Reproducible performance benchmarks over deterministic datasets.

The runner imports a seeded dataset and measures the cost of the main
operations: import throughput, retrieval latency, graph construction,
intelligence generation, report rendering, and (when the optional API/SDK extras
are installed) in-process API and SDK latency. Datasets are deterministic;
timings naturally vary between machines, so reports surface the data volume and
per-operation statistics rather than fabricated fixed numbers.
"""

from __future__ import annotations

import statistics
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from ..intelligence import AnalysisFilters
from ..retrieval import RetrievalQuery
from ..services import (
    GraphService,
    IntelligenceService,
    MeetingService,
    RetrievalService,
)
from .datasets import DatasetSpec, write_dataset

_QUERY_TERMS: tuple[str, ...] = (
    "risk",
    "decided",
    "assigned",
    "assuming",
    "still open",
    "Project Atlas",
)


@dataclass(frozen=True)
class BenchmarkResult:
    """Timing statistics for a single benchmarked operation."""

    name: str
    unit: str
    count: int
    samples: tuple[float, ...]
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def total_seconds(self) -> float:
        """Return the total measured time across all samples."""
        return sum(self.samples)

    @property
    def mean_ms(self) -> float:
        """Return the mean per-sample latency in milliseconds."""
        return statistics.fmean(self.samples) * 1000.0 if self.samples else 0.0

    @property
    def median_ms(self) -> float:
        """Return the median per-sample latency in milliseconds."""
        return statistics.median(self.samples) * 1000.0 if self.samples else 0.0

    @property
    def min_ms(self) -> float:
        """Return the fastest per-sample latency in milliseconds."""
        return min(self.samples) * 1000.0 if self.samples else 0.0

    @property
    def max_ms(self) -> float:
        """Return the slowest per-sample latency in milliseconds."""
        return max(self.samples) * 1000.0 if self.samples else 0.0

    @property
    def throughput(self) -> float:
        """Return processed work units per second (``count`` / total time)."""
        total = self.total_seconds
        return self.count / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, object]:
        """Serialise the result into JSON-compatible primitives."""
        return {
            "name": self.name,
            "unit": self.unit,
            "count": self.count,
            "samples": len(self.samples),
            "mean_ms": round(self.mean_ms, 4),
            "median_ms": round(self.median_ms, 4),
            "min_ms": round(self.min_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "throughput_per_s": round(self.throughput, 4),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BenchmarkReport:
    """A complete benchmark run for one dataset."""

    dataset: str
    iterations: int
    results: tuple[BenchmarkResult, ...]
    summary: dict[str, object] = field(default_factory=dict)

    def result(self, name: str) -> BenchmarkResult | None:
        """Return the named result, if present."""
        for result in self.results:
            if result.name == name:
                return result
        return None

    def to_dict(self) -> dict[str, object]:
        """Serialise the report into JSON-compatible primitives."""
        return {
            "dataset": self.dataset,
            "iterations": self.iterations,
            "summary": dict(self.summary),
            "results": [result.to_dict() for result in self.results],
        }

    def render_text(self) -> str:
        """Render a compact, human-readable benchmark table."""
        lines = [
            f"Benchmark report: {self.dataset} (iterations={self.iterations})",
            (
                f"  meetings={self.summary.get('meetings')} "
                f"memories={self.summary.get('memories')} "
                f"db_size_bytes={self.summary.get('db_size_bytes')} "
                f"peak_memory_bytes={self.summary.get('peak_memory_bytes')}"
            ),
            "",
            f"  {'operation':<22}{'count':>8}{'mean ms':>12}{'p50 ms':>12}{'per/s':>14}",
        ]
        for result in self.results:
            lines.append(
                f"  {result.name:<22}{result.count:>8}{result.mean_ms:>12.3f}"
                f"{result.median_ms:>12.3f}{result.throughput:>14.2f}"
            )
        return "\n".join(lines)


class BenchmarkRunner:
    """Generate a dataset and benchmark the core operations against it."""

    def __init__(
        self,
        spec: DatasetSpec,
        *,
        iterations: int = 1,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if iterations < 1:
            raise ValueError(f"iterations must be >= 1, got {iterations}")
        self.spec = spec
        self.iterations = iterations
        self._clock = clock

    def _time(self, func: Callable[..., object], *args: object, **kwargs: object) -> float:
        start = self._clock()
        func(*args, **kwargs)
        return self._clock() - start

    def run(self) -> BenchmarkReport:
        """Run every benchmark and return a populated report."""
        with TemporaryDirectory(prefix="mm-bench-") as tmp:
            workdir = Path(tmp)
            dataset_dir = workdir / "dataset"
            write_dataset(self.spec, dataset_dir)
            results: list[BenchmarkResult] = []

            import_samples: list[float] = []
            meetings = 0
            memories = 0
            db_path = workdir / "bench-0.db"
            for index in range(self.iterations):
                db_path = workdir / f"bench-{index}.db"
                service = MeetingService(db_path)
                duration = self._time(service.import_path, dataset_dir, recursive=True)
                import_samples.append(duration)
                stats = service.stats()
                meetings = stats.meetings
                memories = stats.memories
            results.append(
                BenchmarkResult(
                    name="import",
                    unit="meeting",
                    count=meetings * self.iterations,
                    samples=tuple(import_samples),
                    metadata={"memories": memories},
                )
            )

            results.append(self._bench_retrieval(db_path))
            results.append(self._bench_graph(db_path))
            results.append(self._bench_intelligence(db_path))
            results.append(self._bench_report(db_path))
            results.extend(self._bench_api_sdk(db_path))

            peak = self._measure_memory(db_path)
            summary: dict[str, object] = {
                "meetings": meetings,
                "memories": memories,
                "db_size_bytes": db_path.stat().st_size,
                "peak_memory_bytes": peak,
            }
            return BenchmarkReport(
                dataset=self.spec.name,
                iterations=self.iterations,
                results=tuple(results),
                summary=summary,
            )

    def _bench_retrieval(self, db_path: Path) -> BenchmarkResult:
        service = RetrievalService(db_path)
        samples: list[float] = []
        for _ in range(self.iterations):
            for term in _QUERY_TERMS:
                query = RetrievalQuery(text=term, limit=20)
                samples.append(self._time(service.search, query))
        return BenchmarkResult(
            name="retrieval",
            unit="query",
            count=len(samples),
            samples=tuple(samples),
        )

    def _bench_graph(self, db_path: Path) -> BenchmarkResult:
        service = GraphService(db_path)
        samples = [self._time(service.summary) for _ in range(self.iterations)]
        summary = service.summary()
        return BenchmarkResult(
            name="graph",
            unit="build",
            count=self.iterations,
            samples=tuple(samples),
            metadata={"nodes": summary.nodes, "edges": summary.edges},
        )

    def _bench_intelligence(self, db_path: Path) -> BenchmarkResult:
        service = IntelligenceService(db_path)
        filters = AnalysisFilters()
        samples = [self._time(service.report, filters) for _ in range(self.iterations)]
        report = service.report(filters)
        return BenchmarkResult(
            name="intelligence",
            unit="report",
            count=self.iterations,
            samples=tuple(samples),
            metadata={"insights": len(report.insights)},
        )

    def _bench_report(self, db_path: Path) -> BenchmarkResult:
        service = IntelligenceService(db_path)
        report = service.report(AnalysisFilters())
        samples = [self._time(service.render, report, "markdown") for _ in range(self.iterations)]
        return BenchmarkResult(
            name="report_render",
            unit="render",
            count=self.iterations,
            samples=tuple(samples),
        )

    def _bench_api_sdk(self, db_path: Path) -> list[BenchmarkResult]:
        try:
            from ..sdk import MeetingMemoryClient
        except ImportError:  # pragma: no cover - optional extras not installed
            return []
        client = MeetingMemoryClient.local(db=db_path)
        try:
            api_samples = [
                self._time(client.search, "risk", limit=20) for _ in range(self.iterations)
            ]
            sdk_samples = [self._time(client.stats) for _ in range(self.iterations)]
        finally:
            client.close()
        return [
            BenchmarkResult(
                name="api_search",
                unit="request",
                count=self.iterations,
                samples=tuple(api_samples),
            ),
            BenchmarkResult(
                name="sdk_stats",
                unit="request",
                count=self.iterations,
                samples=tuple(sdk_samples),
            ),
        ]

    def _measure_memory(self, db_path: Path) -> int:
        tracemalloc.start()
        IntelligenceService(db_path).report(AnalysisFilters())
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return peak


def run_benchmarks(spec: DatasetSpec, *, iterations: int = 1) -> BenchmarkReport:
    """Convenience wrapper that builds a :class:`BenchmarkRunner` and runs it."""
    return BenchmarkRunner(spec, iterations=iterations).run()
