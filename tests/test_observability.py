"""Tests for the observability metrics and profiling utilities (Phase 9)."""

from __future__ import annotations

import json
import tracemalloc

import pytest

from meeting_memory.observability import (
    Counter,
    Gauge,
    HealthCheck,
    HealthSnapshot,
    Histogram,
    MetricsCollector,
    SystemMetrics,
    Timer,
    profile_cpu,
    profile_memory,
)
from meeting_memory.observability.profiling import (
    PipelineTimer,
    PipelineTiming,
    SlowQueryDetector,
)

# -- metrics primitives -------------------------------------------------------


def test_counter() -> None:
    counter = Counter("c")
    counter.inc()
    counter.inc(4)
    assert counter.value == 5
    counter.reset()
    assert counter.value == 0
    with pytest.raises(ValueError, match="decrease"):
        counter.inc(-1)


def test_gauge() -> None:
    gauge = Gauge("g")
    gauge.set(10)
    gauge.inc(2)
    gauge.dec(5)
    assert gauge.value == 7


def test_histogram_statistics() -> None:
    histogram = Histogram("h")
    for value in (0.001, 0.02, 0.2, 0.9):
        histogram.observe(value)
    assert histogram.count == 4
    assert histogram.sum == pytest.approx(1.121)
    assert histogram.mean == pytest.approx(0.28025)
    assert histogram.min == 0.001
    assert histogram.max == 0.9
    assert histogram.percentile(0.5) > 0
    snapshot = histogram.snapshot()
    assert snapshot["count"] == 4
    assert "+Inf" in histogram.bucket_counts()
    histogram.reset()
    assert histogram.count == 0


def test_histogram_empty_and_bad_quantile() -> None:
    histogram = Histogram("h")
    assert histogram.mean == 0.0
    assert histogram.min == 0.0
    assert histogram.max == 0.0
    assert histogram.percentile(0.9) == 0.0
    with pytest.raises(ValueError, match="quantile"):
        histogram.percentile(2.0)


def test_timer_context_and_record() -> None:
    ticks = iter([0.0, 0.5])
    timer = Timer("t", clock=lambda: next(ticks))
    with timer.time():
        pass
    assert timer.histogram.count == 1
    assert timer.snapshot()["count"] == 1
    timer.record(0.25)
    assert timer.histogram.count == 2


def test_timer_default_clock() -> None:
    timer = Timer("t")
    timer.record(0.1)
    assert timer.histogram.count == 1


# -- collector ----------------------------------------------------------------


def test_collector_registers_and_reuses() -> None:
    collector = MetricsCollector()
    assert collector.counter("a") is collector.counter("a")
    assert collector.gauge("g") is collector.gauge("g")
    assert collector.histogram("h") is collector.histogram("h")
    assert collector.timer("t") is collector.timer("t")


def test_collector_snapshot_and_json() -> None:
    collector = MetricsCollector()
    collector.counter("imports").inc(3)
    collector.gauge("queue").set(2)
    collector.histogram("lat").observe(0.1)
    collector.timer("op").record(0.05)
    snapshot = collector.snapshot()
    assert snapshot["counters"] == {"imports": 3}
    parsed = json.loads(collector.to_json())
    assert parsed["gauges"]["queue"] == 2


def test_collector_prometheus() -> None:
    collector = MetricsCollector()
    collector.counter("imports").inc(2)
    collector.gauge("queue").set(1.5)
    collector.histogram("lat").observe(0.1)
    collector.timer("op").record(0.05)
    text = collector.to_prometheus()
    assert "# TYPE imports counter" in text
    assert "imports 2" in text
    assert "queue 1.5" in text
    assert "lat_bucket{" in text
    assert "op_seconds_count 1" in text


def test_collector_sanitizes_names() -> None:
    collector = MetricsCollector()
    collector.gauge("9 bad-name").set(1)
    collector.counter("").inc()
    text = collector.to_prometheus()
    assert "_9_bad_name 1" in text
    assert "metric 1" in text


def test_collector_reset() -> None:
    collector = MetricsCollector()
    collector.counter("c").inc()
    collector.reset()
    assert collector.snapshot()["counters"] == {}


# -- health and system --------------------------------------------------------


def test_health_snapshot_ok_and_degraded() -> None:
    ok = HealthSnapshot.build((HealthCheck("db", True),))
    assert ok.status == "ok" and ok.healthy
    degraded = HealthSnapshot.build((HealthCheck("db", True), HealthCheck("disk", False, "low")))
    assert degraded.status == "degraded" and not degraded.healthy
    assert degraded.to_dict()["checks"][1]["detail"] == "low"


def test_system_metrics_capture() -> None:
    metrics = SystemMetrics.capture()
    payload = metrics.to_dict()
    assert payload["max_rss_bytes"] >= 0
    assert payload["thread_count"] >= 1
    assert payload["python_version"]


def test_system_metrics_linux_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("meeting_memory.observability.metrics.sys.platform", "linux")
    assert SystemMetrics.capture().max_rss_bytes >= 0


def test_system_metrics_darwin_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("meeting_memory.observability.metrics.sys.platform", "darwin")
    assert SystemMetrics.capture().max_rss_bytes >= 0


# -- profiling ----------------------------------------------------------------


def _work(n: int) -> int:
    return sum(i * i for i in range(n))


def test_profile_cpu() -> None:
    result, profile = profile_cpu(_work, 20000, top=3)
    assert result == _work(20000)
    assert len(profile.entries) <= 3
    assert profile.total_seconds >= 0
    assert profile.to_dict()["entries"][0]["function"]


def test_profile_memory() -> None:
    result, profile = profile_memory(lambda: [list(range(100)) for _ in range(20)], top=5)
    assert len(result) == 20
    assert profile.peak_bytes > 0
    assert profile.to_dict()["current_bytes"] >= 0


def test_profile_memory_when_already_tracing() -> None:
    tracemalloc.start()
    try:
        _, profile = profile_memory(lambda: list(range(50)), top=2)
    finally:
        tracemalloc.stop()
    assert profile.peak_bytes >= 0
    # profile_memory must leave the outer tracer running.
    assert not tracemalloc.is_tracing()


def test_pipeline_timer() -> None:
    ticks = iter([0.0, 1.0, 1.0, 3.0])
    timer = PipelineTimer(clock=lambda: next(ticks))
    with timer.stage("load"):
        pass
    assert timer.measure("process", lambda: 42) == 42
    result = timer.result()
    assert [stage.name for stage in result.stages] == ["load", "process"]
    assert result.total_seconds == pytest.approx(3.0)
    slowest = result.slowest()
    assert slowest is not None and slowest.name == "process"
    payload = result.to_dict()
    assert payload["slowest"] == "process"
    assert payload["stages"][0]["name"] == "load"


def test_pipeline_timing_empty() -> None:
    timing = PipelineTiming(stages=())
    assert timing.slowest() is None
    assert timing.to_dict()["slowest"] is None


def test_slow_query_detector() -> None:
    ticks = iter([0.0, 2.0, 2.0, 2.1])
    detector = SlowQueryDetector(1.0, clock=lambda: next(ticks))
    detector.run("slow", lambda: None)
    detector.run("fast", lambda: None)
    labels = [query.label for query in detector.slow_queries]
    assert labels == ["slow"]
    assert detector.to_dict()["threshold_seconds"] == 1.0


def test_slow_query_detector_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError, match="threshold"):
        SlowQueryDetector(-1.0)
