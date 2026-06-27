# Performance & benchmarking

Phase 9 adds reproducible benchmark datasets and a benchmark runner. Datasets
are deterministic (seeded), so the *data* is identical on every run; measured
*timings* naturally vary by machine, so treat them as relative measurements
rather than fixed targets.

## Benchmark datasets

Four presets model organizations of increasing size. Each contains multiple
projects and people, recurring (project-specific) risks, evolving decisions,
long weekly timelines, and explicit cross-meeting references.

| Preset | Projects | People | Meetings | Utterances/meeting |
| --- | --- | --- | --- | --- |
| `small` | 2 | 4 | 6 | 12 |
| `medium` | 4 | 8 | 40 | 16 |
| `large` | 8 | 14 | 200 | 20 |
| `enterprise` | 12 | 16 | 600 | 24 |

```python
from meeting_memory.benchmarks import get_preset, generate_dataset, write_dataset

spec = get_preset("enterprise")
meetings = generate_dataset(spec)          # in-memory, byte-for-byte reproducible
paths = write_dataset(spec, "/tmp/org")    # or write transcripts to disk
```

Determinism guarantee: `generate_dataset(spec) == generate_dataset(spec)` always
holds, because every generator is seeded from `DatasetSpec.seed`.

## Running benchmarks

```bash
meeting-memory benchmark --dataset medium --iterations 3
meeting-memory benchmark --dataset small --json -o report.json
```

```python
from meeting_memory.benchmarks import get_preset, run_benchmarks

report = run_benchmarks(get_preset("medium"), iterations=3)
print(report.render_text())
data = report.to_dict()
```

## What is measured

| Operation | Unit | Notes |
| --- | --- | --- |
| `import` | meetings/s | Full parse + extract + persist pipeline. |
| `retrieval` | queries/s | Ranked search across a fixed set of query terms. |
| `graph` | builds/s | Rebuild + summarise the knowledge graph. |
| `intelligence` | reports/s | Full insight/metric/recommendation analysis. |
| `report_render` | renders/s | Markdown rendering of a report. |
| `api_search` / `sdk_stats` | requests/s | In-process API/SDK latency (when the `api`/`sdk` extras are installed). |

The report summary also records `meetings`, `memories`, `db_size_bytes`, and
`peak_memory_bytes` (captured with `tracemalloc`).

Each `BenchmarkResult` exposes `mean_ms`, `median_ms`, `min_ms`, `max_ms`, and
`throughput` (work units per second). API/SDK benchmarks are skipped silently if
the optional extras are not installed.

## Profiling

For deeper analysis, profile a single operation:

```bash
meeting-memory profile --db atlas.db --operation intelligence --top 10
meeting-memory profile --operation import --dataset small --json
```

Programmatically:

```python
from meeting_memory.observability import profile_cpu, profile_memory
from meeting_memory.services import IntelligenceService
from meeting_memory.intelligence import AnalysisFilters

result, cpu = profile_cpu(IntelligenceService("atlas.db").report, AnalysisFilters())
result, mem = profile_memory(IntelligenceService("atlas.db").report, AnalysisFilters())
print(cpu.to_dict()["entries"][:5])
print(mem.peak_bytes)
```

`PipelineTimer` records sequential stage timings and `SlowQueryDetector` flags
operations slower than a threshold; both accept an injectable clock for
deterministic testing.
