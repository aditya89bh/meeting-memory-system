# Connector Framework & Automation Engine (Phase 7)

Phase 7 wraps Phases 1–6 in a deterministic **connector framework**. It lets
meeting data be imported from many sources, organizational intelligence be
exported to many destinations, and the whole pipeline be chained together by a
declarative automation engine with scheduling and structured logging.

Like every earlier phase it is **deterministic and standard-library only**: no
LLM APIs, no external schedulers, no network access, and no API credentials. The
bundled connectors read and write local files; future live SaaS connectors
(Slack, Zoom, Notion, Jira, GitHub) are designed to plug into the same
interfaces without changing the core.

## Where it sits in the pipeline

```
                      ┌──────────────── connectors ────────────────┐
sources ─▶ import ─▶ Parser ─▶ Extraction ─▶ Storage ─▶ Retrieval ─▶ Graph ─▶ Intelligence ─▶ export ─▶ destinations
                      └──────────── automation engine (one ExecutionContext) ────────────┘
```

The connector layer never reimplements parsing, extraction, storage, graph, or
intelligence; it orchestrates them. Import connectors feed the existing parser
and `persist_extraction`; export connectors read the `SQLiteMemoryStore` and
`SQLiteGraphStore` and reuse the intelligence and graph renderers.

## Connector interfaces

All interfaces live in `src/meeting_memory/connectors/base.py`. Every connector
exposes the same five-method contract:

| Method | Purpose |
| --- | --- |
| `metadata()` | Return a `ConnectorMetadata` (name, version, type, capabilities, formats). |
| `validate(request)` | Return a list of human-readable problems (empty ⇒ valid). |
| `supports(request)` | Whether the connector can handle the request (default: no validation problems). |
| `execute(request, store, *, logger=None)` | Perform the import/export against the store. |
| `dry_run(request, *, logger=None)` | Preview without writing the destination/store. |

Three concrete interfaces specialise it:

- **`ImportConnector`** → produces an `ImportResult` (files processed, meetings
  imported, memories stored, duplicates, per-file `FileImportOutcome`s).
- **`ExportConnector`** → produces an `ExportResult` (format, destination,
  content, byte count).
- **`AutomationConnector`** → runs against an `ExecutionContext` and returns a
  `ConnectorResult`; the extension point for whole-pipeline plugins.

### Registry and manager

- **`ConnectorRegistry`** registers connectors and resolves them by name, by file
  path (extension → import connector; directory → directory/recursive; `.zip` →
  archive), or by export format. `default_registry()` returns a registry with all
  bundled connectors registered.
- **`ConnectorManager`** is the facade the CLI and automation engine use:
  `import_source`, `dry_run_import`, `export`, and `dry_run_export`. It selects
  the right connector, validates the request (raising `ConnectorValidationError`
  on problems), emits structured logs, and returns the typed result.

### Models

Immutable dataclasses in `src/meeting_memory/connectors/models.py`:
`ConnectorMetadata`, `ConnectorResult`, `ImportRequest`/`ImportResult`,
`ExportRequest`/`ExportResult`, `Schedule`, `StepConfig`, `AutomationJob`,
`StageResult`/`AutomationResult`, and the `ConnectorType`, `ConnectorStatus`,
`ConnectorCapability`, and `ScheduleFrequency` enums. `ConnectorStatus` covers
`success`, `partial`, `skipped`, `failure`, and `dry_run`; a batch with one bad
file aggregates to `partial` while still importing the good files.

## Import connectors

`src/meeting_memory/connectors/importers.py`:

| Name | Capability | Notes |
| --- | --- | --- |
| `text` | file | Plain-text transcript (front-matter aware). |
| `json` | file | JSON transcript via `MeetingParser.parse_json`. |
| `markdown` | file | Markdown notes normalised to `Speaker: text` turns. |
| `csv` | file | CSV action items (owner + action/text columns). |
| `directory` | directory | All supported files in one directory. |
| `recursive-directory` | recursive | All supported files in a directory tree. |
| `batch` | batch | An explicit, ordered list of files (`sources`). |
| `archive` | archive | Every supported file inside a `.zip`. |

Each importer hashes the transcript and asks the store for an existing meeting,
so re-importing the same file is reported as a `skipped` duplicate rather than
re-stored. Malformed input (bad JSON, unreadable files) becomes a per-file
`failure` outcome instead of aborting the run.

## Export connectors

`src/meeting_memory/connectors/exporters.py`:

| Format | Output |
| --- | --- |
| `json` | Full intelligence report serialised as JSON. |
| `markdown` | Intelligence report rendered as Markdown. |
| `report` | Intelligence report rendered as plain text. |
| `html` | Self-contained HTML intelligence report. |
| `csv` | Stored memories as CSV rows. |
| `graph` | Knowledge graph as JSON/Mermaid/DOT (`--output` extension chooses). |
| `summary` | One section per meeting with its memories. |

An export with no `destination` returns its content (printed to stdout by the
CLI); with a `destination` it writes the file and reports the byte count.

## Automation architecture

`src/meeting_memory/connectors/automation.py`:

- **`ExecutionContext`** — the one mutable object shared across a run: the
  database path, the open `SQLiteMemoryStore`, the lazily-built graph store, the
  `ConnectorManager`, the logger, the correlation id, the deterministic `now`,
  and the `dry_run` flag.
- **`PipelineExecutor`** — runs each `StepConfig` in order (`import`, `graph`,
  `intelligence`, `export`), returning a `StageResult` per step and stopping at
  the first hard `failure`.
- **`JobRunner`** — opens the store, builds the context, runs the executor,
  aggregates the stage statuses into an `AutomationResult`, and closes resources.
- **`JobHistory`** — appends each `AutomationResult` to a JSON Lines file beside
  the database (`<db>.jobs.jsonl`) and lists recent runs.
- **`AutomationEngine`** — the top-level entry point: `run_job(job, ...)` and
  `run_file(path, ...)` (which loads and validates a pipeline file first).

Statuses aggregate predictably: any stage `failure` ⇒ run `failure`; otherwise
any `partial` ⇒ `partial`; a dry run ⇒ `dry_run`; else `success`.

## Scheduler

`src/meeting_memory/connectors/scheduler.py` is pure computation — it returns
*when* a job should run; it never sleeps or spawns a daemon.

- `next_run(schedule, after)` → the next run strictly after a moment, or `None`.
- `simulate(schedule, start=..., count=...)` → the next *N* run times.
- Frequencies: `once` (optional `at`), `hourly`, `daily`, `weekly` (Mondays),
  `manual` (never), and `cron`.
- `parse_cron` / `cron_next` implement a five-field subset — `*`, ranges
  (`9-17`), steps (`*/15`), and lists (`1,3,5`), with standard day-of-month /
  day-of-week OR semantics. Impossible expressions raise `ScheduleError`.

Drive real execution by feeding the simulated times to an external timer
(cron/systemd) that calls `meeting-memory automate`.

## Structured logging

`src/meeting_memory/connectors/logging.py` emits immutable `LogRecord`s to a
pluggable `LogSink` (`MemoryLogSink` for tests, `JsonlFileLogSink` for the CLI,
written to `<db>.logs.jsonl`). Each record carries the correlation id, sequence,
level, message, pipeline stage, connector, item count, duration, destination,
warning/error counts, and timestamp — all machine-readable. Wall-clock concerns
(`clock`, `now`) are injected so runs are fully reproducible in tests.
`read_logs(path, correlation_id=..., limit=...)` reads records back.

## Configuration schema

Pipelines are declarative YAML or JSON, parsed by a dependency-free YAML-subset
reader (`config.py`) and validated by `validate_job` before execution.

```yaml
name: daily-intelligence       # job name (default: "pipeline")
enabled: true                  # optional
schedule:                      # optional (default: manual)
  frequency: daily             # once | hourly | daily | weekly | manual | cron
  expression: "0 9 * * 1-5"    # required when frequency is cron
  at: "2026-07-01T09:00:00"    # optional, used by frequency once
steps:                         # required, non-empty, run in order
  - type: import               # import | graph | intelligence | export
    source: examples/history   # import: a file or directory ...
    sources: [a.txt, b.json]   # ... or an explicit batch list
    recursive: true            # import: recurse into subdirectories
    pattern: "*"               # import: glob for directory imports
    deduplicate: true          # import: skip duplicate transcripts
    min_confidence: 0.0        # import: extraction confidence floor
    types: [decision, risk]    # import: restrict memory types
    limit: 100                 # import: cap the number of files
  - type: graph                # (re)build the knowledge graph
  - type: intelligence         # compute the intelligence report
  - type: export
    format: markdown           # json | markdown | report | html | csv | graph | summary
    output: out/report.md      # omit to return content to the caller/stdout
```

Validation problems (unknown step type, import without `source`/`sources`,
export without `format`, cron without/with an invalid `expression`, empty
pipeline) are collected and raised as a single `PipelineConfigError`.

## CLI

| Command | Description |
| --- | --- |
| `import-dir <path>` | Import a directory (`--recursive`, `--pattern`, `--limit`, `--dry-run`). |
| `export` | Export data (`--format`, `--output`, `--dry-run`). |
| `automate <config>` | Run a pipeline file (`--dry-run`); exits non-zero on failure. |
| `jobs` | List recorded automation runs (`--limit`). |
| `schedule <config>` | Show upcoming run times (`--after`, `--count`). |
| `logs` | Show structured logs (`--correlation`, `--limit`). |

All connector commands accept `--db` and `--json`. Examples live in
[`../examples/pipelines/`](../examples/pipelines/).

## Extending: future SaaS connectors

The framework is the integration point for live sources. To add one (for example
a Slack importer):

1. Subclass `ImportConnector` (or `ExportConnector`) and implement the five-method
   contract; normalise the source into a `Meeting` so the existing parser and
   extraction pipeline can be reused unchanged.
2. Declare its `ConnectorMetadata` (name, capabilities, supported formats).
3. Register it on a `ConnectorRegistry` (or extend `register_all`).
4. Reference it from pipeline steps by name.

Because resolution, validation, dry-run, logging, scheduling, and history are all
provided by the framework, a new connector only implements the source-specific
read/write — everything else composes for free. Network access, authentication,
and credentials would be introduced inside such a connector, leaving the
deterministic core untouched.
