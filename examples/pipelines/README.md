# Connector & automation examples

Phase 7 adds a deterministic connector framework: importers pull transcripts from
files, directories, and archives; exporters push reports, memories, graphs, and
summaries to many formats; and the automation engine wires the whole pipeline
together (`import -> graph -> intelligence -> export`). Everything stays
standard-library only — no external schedulers, no network, no credentials.

These examples reuse the three Project Atlas meetings in
[`examples/history`](../history/README.md).

## Directory ingestion

Import every supported transcript (`txt`, `json`, `md`, `csv`) in a directory:

```bash
meeting-memory import-dir examples/history --db atlas.db
meeting-memory import-dir examples/history --db atlas.db --recursive --dry-run
```

```
directory: success
4 files processed
4 meetings imported
28 memories stored
```

## Markdown report export

Export organizational intelligence in any registered format:

```bash
meeting-memory export --format markdown --db atlas.db -o atlas-report.md
meeting-memory export --format html --db atlas.db -o atlas-report.html
meeting-memory export --format csv --db atlas.db -o atlas-memories.csv
```

## Graph export

The knowledge graph exports as JSON, Mermaid, or DOT:

```bash
meeting-memory export --format graph --db atlas.db -o atlas-graph.json
meeting-memory export --format mermaid --db atlas.db
```

## Daily import + report pipeline

[`daily.yaml`](daily.yaml) imports a directory, builds the graph, runs the
intelligence engine, and writes a Markdown report, JSON report, and graph export.

```bash
meeting-memory automate examples/pipelines/daily.yaml --db atlas.db --dry-run
meeting-memory automate examples/pipelines/daily.yaml --db atlas.db
```

```
job daily: success
correlation: 3f76736f0979
stages: 6
  - import [success] (28 items)
  - graph [success] (40 items)
  - intelligence [success] (2 items)
  - export [success] (2 items)
  - export [success] (2 items)
  - export [success] (40 items)
```

## Weekly report pipeline (cron schedule)

[`weekly.yaml`](weekly.yaml) runs on a cron schedule (`0 9 * * 1` — every Monday
at 09:00) and produces an HTML report plus per-meeting summaries. Preview the
upcoming run times without starting any daemon:

```bash
meeting-memory schedule examples/pipelines/weekly.yaml --count 4
```

```
job: weekly-report
frequency: cron
2026-06-29T09:00:00+00:00
2026-07-06T09:00:00+00:00
2026-07-13T09:00:00+00:00
2026-07-20T09:00:00+00:00
```

## Batch organization analysis

[`batch.json`](batch.json) shows the JSON pipeline format and a batch import of an
explicit file list, exporting a plain-text report and a CSV of every memory.

```bash
meeting-memory automate examples/pipelines/batch.json --db atlas.db
```

## Inspecting runs and logs

Every run records machine-readable structured logs and a job-history entry beside
the database (`atlas.db.logs.jsonl`, `atlas.db.jobs.jsonl`):

```bash
meeting-memory jobs --db atlas.db
meeting-memory logs --db atlas.db --limit 10
meeting-memory logs --db atlas.db --json
```
