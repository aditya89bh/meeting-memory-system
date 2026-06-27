# Meeting Memory System

[![CI](https://github.com/aditya89bh/meeting-memory-system/actions/workflows/ci.yml/badge.svg)](https://github.com/aditya89bh/meeting-memory-system/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-2a6db2.svg)](https://mypy-lang.org/)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](#development)

**Turn raw meeting transcripts into durable, queryable institutional memory** — then
search it, graph it, and mine it for insights. The system extracts the *memory
primitives* of every meeting (decisions, commitments, open loops, risks, assumptions,
questions, and facts) and connects them across meetings so you can answer questions like
*"which risks keep coming back?"* and *"which decisions have we reversed?"*.

It is **100% deterministic and local-first**: no LLM APIs, no embeddings, no vector
database, no network calls. The same transcripts always produce the same memory, graph,
and reports — which makes it auditable, testable, and cheap to run.

## See it in 60 seconds

```bash
pip install -e .
meeting-memory demo
```

The demo imports example meetings, builds memory, runs a search, builds the graph,
generates intelligence, and renders a report — start to finish in under a minute.

## Why it's different

- **Deterministic, not generative.** Rule-based extraction and analysis — reproducible
  and explainable, never a black box. It is intentionally *not* a meeting summarizer.
- **Cross-meeting memory.** Value compounds across meetings: recurring risks, revisited
  decisions, and aging commitments only emerge when memory spans time.
- **One system, four surfaces.** A shared service layer powers a [CLI](docs/tutorials/getting-started.md),
  a [REST API](docs/tutorials/rest-api.md), a [Python SDK](docs/tutorials/python-sdk.md),
  and a web dashboard — all with identical behaviour.
- **Production-ready.** Benchmarks, observability, backup/recovery, and Docker
  deployment ship in the box.

## Documentation

| Start here | Build | Operate |
|---|---|---|
| [Tutorials](docs/tutorials/) | [Architecture](docs/architecture.md) | [Deployment](docs/deployment.md) |
| [Notebooks](notebooks/) | [Database schema](docs/schema.md) | [Backup & recovery](docs/backup.md) |
| [Example organizations](examples/organizations/) | [REST API](docs/api.md) · [SDK](docs/sdk.md) | [Performance](docs/performance.md) · [Benchmarks](docs/benchmarks.md) |
| [Case studies](docs/case-studies/) | [CLI reference](#quick-start) | [Replay](docs/replay.md) |

See also: [CHANGELOG](CHANGELOG.md) · [ROADMAP](ROADMAP.md) · [CONTRIBUTING](CONTRIBUTING.md) · [SECURITY](SECURITY.md).

## Features

- **Typed domain models** for meetings, speakers, utterances, timestamps, and
  metadata (`Meeting`, `Speaker`, `Utterance`, `Timestamp`, `Metadata`).
- **Extensible transcript loader** supporting `.txt` and `.json`, with a small
  registry so new on-disk formats can be added without touching the parser.
- **Format-aware parser** that understands speaker labels, leading/trailing
  timestamps, multi-line utterances, and an optional metadata front-matter block.
- **Deterministic memory extraction** of seven primitives via a configurable,
  rule-based extractor registry with evidence spans and confidence scores.
- **Confidence scoring, deduplication, and validation** built into the
  extraction pipeline, with type and minimum-confidence filtering.
- **Semantic validation** with descriptive exceptions for empty meetings,
  duplicate timestamps, and invalid speakers.
- **Normalization utilities** that clean whitespace, line endings, speaker
  labels, and timestamp formatting without changing semantic content.
- **Statistics helpers** for utterance/speaker/word counts and meeting duration.
- **Durable memory store** backed by SQLite with a migrated, indexed schema,
  foreign keys, a meeting registry, a deterministic query API, a memory
  lifecycle, and transcript/memory-level duplicate detection.
- **Deterministic retrieval engine** with a query planner, AND-combined keyword
  and metadata filtering, a transparent six-factor ranking model, temporal
  queries (`before`/`after`/`between`/`latest`/`oldest`/`timeline`), configurable
  context windows, and rule-based per-result explanations.
- **Organizational memory graph** with deterministic entity and relationship
  extraction, cross-meeting linking, traversal (`neighbors`/`related`/`find_path`/
  `connected_components`), decision and risk lineage, and JSON/Mermaid/DOT export.
- **Organizational intelligence engine** with a plugin architecture
  (insight/metric/recommendation/report providers), deterministic decision,
  commitment, and risk analyses, organizational-health scoring, evidence-backed
  recommendations, and JSON/Markdown/plain-text reports.
- **Connector framework & automation engine** with a connector registry, file
  import connectors (text/JSON/Markdown/CSV, directory/recursive/batch/zip),
  export connectors (JSON/Markdown/HTML/CSV/graph/summaries), declarative
  YAML/JSON pipelines, a deterministic scheduler (once/hourly/daily/weekly/cron
  subset with simulation), structured machine-readable logging, and job history.
- **A reusable platform layer** built on one shared service layer that the CLI,
  REST API, Python SDK, and web dashboard all call: a typed FastAPI application
  (health/version, meetings, memories, search, graph, intelligence, automation),
  request/response schemas with structured errors and pagination, observability
  middleware (correlation ids, timing, version headers, structured logs),
  OpenAPI with Swagger UI and ReDoc, a `MeetingMemoryClient` SDK with identical
  local (in-process) and HTTP transports, and a lightweight server-rendered
  dashboard.
- **A production-operations layer** with seeded benchmark datasets and a
  reproducible benchmark runner, a deterministic replay engine, dependency-free
  observability (counters/gauges/histograms/timers, JSON and Prometheus export),
  CPU/memory profiling and slow-query detection, checksummed database backups and
  logical snapshots with recovery validation, and Docker/Compose deployment.
- **A command-line interface** with `parse`, `extract`, `import`, `list`, `show`,
  `meetings`, `stats`, `search`, `timeline`, `explain`, `graph`, `neighbors`,
  `path`, `export-graph`, `insights`, `metrics`, `recommendations`, `report`,
  `import-dir`, `export`, `automate`, `jobs`, `schedule`, `logs`, `benchmark`,
  `replay`, `backup`, `restore`, and `profile` commands
  that emit human or JSON output.
- **100% test coverage**, fully type-checked (`mypy --strict`) and linted (`ruff`).

## Installation

The project targets Python 3.10+ and uses a standard `pyproject.toml`.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package (add the dev extra for tests/linting/type-checking)
pip install -e ".[dev]"

# To run the REST API / dashboard or the SDK over HTTP, add the api/sdk extras
pip install -e ".[api,sdk]"
```

## Quick start

### Command line

```bash
# Parse a transcript and print structured JSON
meeting-memory parse meeting.txt

# Include descriptive statistics and write the result to a file
meeting-memory parse meeting.json --stats --output meeting.parsed.json

# Skip semantic validation, or allow duplicate timestamps
meeting-memory parse meeting.txt --no-validate
meeting-memory parse meeting.json --allow-duplicate-timestamps

# Extract memory records (decisions, commitments, risks, ...)
meeting-memory extract examples/startup_weekly.txt --indent 2

# Only certain types, above a confidence floor, written to a file
meeting-memory extract meeting.txt --types decision,commitment,risk \
    --min-confidence 0.7 --output result.json

# Persist meetings into a shared database, then query across all of them
meeting-memory import examples/history/meeting1.txt --db atlas.db
meeting-memory import examples/history/meeting2.txt --db atlas.db
meeting-memory list --db atlas.db --type risk          # recurring risks
meeting-memory show atlas:decision:0 --db atlas.db      # one memory in detail
meeting-memory meetings --db atlas.db                   # the meeting registry
meeting-memory stats --db atlas.db --json               # aggregate counts

# Search organizational memory across every imported meeting
meeting-memory search postgres --db atlas.db            # ranked keyword search
meeting-memory search --speaker Alice --type decision --db atlas.db
meeting-memory search --type risk --status active --db atlas.db
meeting-memory timeline --type risk --db atlas.db       # chronological history
meeting-memory explain meeting1:decision:1 --db atlas.db  # why + context

# Build and explore the organizational memory graph
meeting-memory graph --db atlas.db                      # node/edge counts
meeting-memory neighbors project:atlas --db atlas.db    # everything around a node
meeting-memory path person:lena project:atlas --db atlas.db  # shortest path
meeting-memory export-graph --db atlas.db --format mermaid    # diagram
```

### Library

```python
from meeting_memory.parser import parse_file, parse_text, validate_meeting
from meeting_memory.utils import compute_statistics

meeting = parse_file("meeting.txt")
validate_meeting(meeting)  # raises a ValidationError subclass if invalid

for utterance in meeting:
    stamp = utterance.timestamp.label if utterance.timestamp else "--:--:--"
    print(f"[{stamp}] {utterance.speaker.name}: {utterance.text}")

stats = compute_statistics(meeting)
print(stats.speaker_utterance_counts)
```

## Supported transcript formats

### Plain text

Each turn is a line of the form `Speaker: text`. Timestamps may lead or trail the
speaker label, and lines that do not start a new turn are merged into the
previous utterance as continuations. An optional `---` delimited front-matter
block at the top carries metadata.

```text
---
title: Weekly Sync
date: 2026-06-27
team: Apollo
---
[00:00:05] Alice: Hello everyone, thanks for joining.
Bob [00:00:12]: Hi Alice — quick note before we start,
this line continues Bob's previous utterance.
Carol: No timestamp here, and that's fine.
```

All of the following timestamp shapes are recognised:

| Example                 | Meaning                          |
| ----------------------- | -------------------------------- |
| `[00:01:05] Alice: ...` | leading, bracketed `HH:MM:SS`    |
| `Alice [00:01:05]: ...` | trailing, bracketed              |
| `Alice 00:01:05: ...`   | trailing, plain                  |
| `Alice 02:30: ...`      | `MM:SS` (interpreted as minutes) |

### JSON

A JSON object with an `utterances` array (or a bare array of utterance objects).
Speaker, text, and timestamp fields accept a few common aliases.

```json
{
  "title": "Standup",
  "date": "2026-06-27",
  "metadata": { "room": "A1" },
  "utterances": [
    { "speaker": "Carol", "text": "Morning all.", "timestamp": "00:00:05" },
    { "name": "Dave", "content": "Hi", "time": 65 }
  ]
}
```

- Speaker keys: `speaker`, `name`, `speaker_name`
- Text keys: `text`, `utterance`, `content`, `message`
- Timestamp keys: `timestamp`, `time`, `start` — a string (`"00:01:05"`) or a
  number of seconds (`65`).

## Output shape

`meeting-memory parse` emits a JSON document like:

```json
{
  "metadata": {
    "title": "Weekly Sync",
    "date": "2026-06-27",
    "source_path": "meeting.txt",
    "source_format": "txt",
    "extra": { "team": "Apollo" }
  },
  "speakers": ["Alice", "Bob", "Carol"],
  "utterances": [
    {
      "index": 0,
      "speaker": "Alice",
      "text": "Hello everyone, thanks for joining.",
      "timestamp": { "total_seconds": 5.0, "label": "00:00:05" }
    }
  ]
}
```

With `--stats`, a `"statistics"` object is added containing utterance, speaker,
and word counts plus the meeting duration.

## Extracting meeting memory (Phase 2)

Phase 2 extracts seven kinds of memory primitive:

| Type         | What it captures                          | Example trigger phrases                        |
| ------------ | ----------------------------------------- | ---------------------------------------------- |
| `decision`   | A choice the group settled on             | "we decided", "approved", "let's go with"      |
| `commitment` | An action someone agreed to take          | "I will", "can you", "assigned to", "by Friday"|
| `open_loop`  | An unresolved thread needing attention    | "pending", "follow up", "TBD", "to be confirmed"|
| `risk`       | A risk, concern, blocker, or dependency   | "risk", "blocker", "might fail", "dependency"  |
| `assumption` | An assumption the discussion relied on    | "assuming", "we assume", "if this holds"       |
| `question`   | An explicit question                      | a trailing "?", "should we", "the question is" |
| `fact`       | An important factual statement            | customer / metric / requirement / timeline language |

Each extracted record carries full provenance: a stable `memory_id`, its
`memory_type`, the utterance `text`, the `speaker`, the `meeting_id`, the
`utterance_index`, an `evidence` span (the exact substring that triggered it), a
bounded `confidence` in `[0.0, 1.0]`, an `extracted_at` timestamp, and optional
`metadata` (commitments also carry `owner` and `due`).

### Library

```python
from datetime import datetime, timezone

from meeting_memory.parser import parse_file
from meeting_memory.extraction import ExtractionConfig, MemoryType, extract_memories

meeting = parse_file("examples/startup_weekly.txt")

config = ExtractionConfig(
    enabled_types=frozenset({MemoryType.DECISION, MemoryType.COMMITMENT}),
    min_confidence=0.7,
    deduplicate=True,
)
result = extract_memories(meeting, config=config)

print(result.total, result.counts())
for memory in result.memories:
    print(f"{memory.memory_type}: {memory.text} (conf={memory.confidence})")
```

### `extract` output shape

```json
{
  "meeting_id": "startup_weekly",
  "meeting": { "title": "Startup Weekly Sync", "date": "2026-01-12", "...": "..." },
  "total": 9,
  "counts": { "decision": 2, "commitment": 1, "risk": 1, "...": "..." },
  "memories": {
    "decision": [
      {
        "memory_id": "startup_weekly:decision:1",
        "memory_type": "decision",
        "text": "We decided to move the launch to February 3rd.",
        "speaker": "Priya",
        "meeting_id": "startup_weekly",
        "utterance_index": 1,
        "evidence": { "utterance_index": 1, "start": 0, "end": 10, "text": "We decided" },
        "confidence": 0.95,
        "extracted_at": "2026-01-15T09:00:00+00:00",
        "metadata": { "trigger": "We decided" }
      }
    ]
  },
  "warnings": []
}
```

Runnable examples live in [`examples/`](examples/) with reference outputs in
[`examples/outputs/`](examples/outputs/). Useful `extract` flags:
`--types`, `--min-confidence`, `--no-deduplicate`, `--output`, `--indent`, and
`--now` (stamp a fixed timestamp for reproducible output).

See [`docs/extraction.md`](docs/extraction.md) for the full pipeline, memory
schema, supported phrases, confidence model, and limitations.

### Limitations of deterministic extraction

This phase trades recall and nuance for determinism and auditability:

- It matches **explicit trigger phrases**, so paraphrased or implicit statements
  are missed, and unusual phrasings of a decision/commitment will not be caught.
- It cannot do **cross-utterance reasoning**: a question that is later answered is
  still reported as a question, and genuinely unanswered questions are not
  inferred (only explicit open-loop language is matched).
- Trigger words can produce **false positives** (e.g. "risk" used casually).
  Confidence scores and `--min-confidence` help callers manage this trade-off.
- It does **no** semantic understanding, summarization, or normalization of
  meaning. A future LLM-backed extractor is a planned extension point (see the
  docs) that can reuse the same models, pipeline, and validation.

## Persistent meeting memory (Phase 3)

Phase 3 turns one-shot extraction into durable organizational memory. The
`import` command runs the full pipeline and persists the result:

```
Load ──▶ Parse ──▶ Extract ──▶ Persist ──▶ Import summary
```

```text
$ meeting-memory import examples/history/meeting1.txt --db atlas.db
Meeting imported: meeting1
13 memories stored
5 facts
3 decisions
1 commitment
1 risk
1 question
1 assumption
1 open loop
```

### Database schema

Everything lives in a single SQLite file with a versioned, migrated schema
(`PRAGMA user_version`), foreign keys, and indexes on the common query columns:

| Table      | Purpose                                                              |
| ---------- | ------------------------------------------------------------------- |
| `meetings` | Registry: id, title, date, source, duration, participants, hash     |
| `memories` | One row per extracted memory, with `status` and `content_hash`      |
| `evidence` | Evidence spans pointing back at the source utterance (FK → memories)|
| `metadata` | Generic key/value rows (e.g. commitment `owner`/`due`)              |

### Query API

The store exposes a deterministic query interface; every filter AND-combines:

```python
from meeting_memory.storage import MemoryQuery, MemoryStatus, SQLiteMemoryStore

with SQLiteMemoryStore("atlas.db") as store:
    store.find_by_type("decision")
    store.find_by_speaker("Alice")
    store.find_by_meeting("meeting1")
    store.find_by_confidence(0.8)
    store.find_active()
    store.find_between_dates("2026-02-01", "2026-02-28")

    # richer combinations via MemoryQuery
    store.query(MemoryQuery(
        memory_types=frozenset({"commitment"}),
        statuses=frozenset({MemoryStatus.ACTIVE}),
        speakers=frozenset({"Marco"}),
    ))
```

### Memory lifecycle

Each memory has a `status` (initially `ACTIVE`) and can move through the
lifecycle with `archive`, `resolve`, `supersede`, `mark_deleted`, and `restore`:

```
ACTIVE ──▶ ARCHIVED / RESOLVED / SUPERSEDED / DELETED ──▶ (restore) ──▶ ACTIVE
```

`supersede(old_id, new_id)` records a pointer (`superseded_by`) so a replaced
decision still links to the one that replaced it.

### Duplicate detection

Two deterministic layers prevent duplicate imports:

- **Meeting level** — the transcript hash in the registry makes re-importing the
  same file a no-op (reported as already imported).
- **Memory level** — within a meeting, memories sharing a content hash (same type
  and normalized text) within a confidence threshold are collapsed. The same
  point may still recur across *different* meetings, which is what makes "which
  risks keep appearing?" answerable.

### Limitations

- Storage is single-file SQLite, intended for local/CLI use; it is not a
  concurrent multi-writer server.
- Duplicate detection is exact-hash based on normalized text — it does not detect
  semantically similar paraphrases (that would require Phase-2's deliberately
  excluded semantic layer).

See [`docs/storage.md`](docs/storage.md) for the architecture, full schema,
migration strategy, query interface, and future extensions. A runnable
multi-meeting walkthrough lives in [`examples/history/`](examples/history/).

## Retrieving meeting memory (Phase 4)

Phase 4 searches the persistent store. The pipeline is deterministic end to end:

```
RetrievalQuery ──▶ plan ──▶ filter (AND) ──▶ rank ──▶ order ──▶ paginate
                                                │
                                  context + explanation ─┘
```

### Search

```bash
meeting-memory search postgres --db atlas.db --type decision
```

```text
meeting1:decision:1  (0.890)  2026-02-02  [decision] active  Priya: We decided to build Atlas on PostgreSQL for the first release.
  ✓ memory type decision
  ✓ keyword "postgres"
```

The **query planner** maps free text onto filters deterministically: memory-type
words (`decision`, `risks`, `open loop`), lifecycle statuses (`active`,
`resolved`), month names (`march`), and known speaker/participant names are
recognised; everything else (minus stopwords) becomes keyword terms. Combined
with the explicit `--type`/`--speaker`/`--status`/`--meeting`/`--min-confidence`
options, every filter is AND-combined.

### Ranking overview

Each result gets a score in `[0.0, 1.0]` from a fixed weighted sum of six
transparent components:

| Component   | Weight | Meaning                                            |
| ----------- | ------ | -------------------------------------------------- |
| text match  | 0.30   | fraction of query terms found in the memory body   |
| exact phrase| 0.15   | the multi-word query appears verbatim              |
| confidence  | 0.20   | the memory's extraction confidence                 |
| recency     | 0.15   | newer meetings rank higher                         |
| status      | 0.10   | `active` > `resolved` > `archived` > ...           |
| meeting     | 0.10   | query terms found in the meeting title/participants|

Equal scores are broken with stable, deterministic ordering (meeting date, then
`created_at`, then `memory_id`), so identical inputs always produce identical
output.

### Timeline queries

```bash
meeting-memory timeline --type risk --db atlas.db
meeting-memory timeline --between 2026-02-01 2026-02-28 --db atlas.db
```

The engine also offers `before`, `after`, `between`, `latest`, and `oldest`
helpers in the library. A timeline lists matches oldest-first, which makes
recurring items (such as a risk raised every week) easy to see.

### Explanation output

Every result explains *why* it matched, derived from the data alone:

```bash
meeting-memory explain meeting1:decision:1 --db atlas.db
```

```text
matched because:
  ✓ speaker Priya
  ✓ memory type decision
  ✓ status active
context:
    [0] Priya: Welcome to the Project Atlas kickoff, let's set direction.
  > [1] Priya: We decided to build Atlas on PostgreSQL for the first release.
    [2] Marco: I will set up the staging environment by next Friday.
```

`--context N` configures how many surrounding utterances to assemble (the source
transcript is re-parsed deterministically; if it is unavailable the window
degrades gracefully to the memory's own text).

### Library

```python
from meeting_memory.retrieval import MemoryRetriever, RetrievalQuery
from meeting_memory.storage import SQLiteMemoryStore

with SQLiteMemoryStore("atlas.db") as store:
    retriever = MemoryRetriever(store)
    result = retriever.retrieve(
        RetrievalQuery(text="postgres", memory_types=frozenset({"decision"}), context_size=1)
    )
    for ranked in result.ranked:
        print(ranked.score, ranked.memory.text)
        print(ranked.explanation.lines())
```

### Limitations

- Matching is **lexical**: keyword terms are substring-matched and AND-combined,
  so paraphrases and synonyms are not retrieved (no embeddings or semantic search).
- The planner resolves names against the speakers/participants already in the
  store; unknown names fall back to keyword terms.
- Context assembly re-reads the original transcript by path, so a moved or deleted
  source yields a memory-only context window.

See [`docs/retrieval.md`](docs/retrieval.md) for the architecture, ranking
strategy, query planner, retrieval pipeline, context assembly, and the planned
semantic-search extension. Runnable search/timeline/explain examples live in
[`examples/retrieval/`](examples/retrieval/).

## Organizational memory graph (Phase 5)

Phase 5 links everything in the store into a typed, directed graph. It is built
deterministically from the stored memories — graph commands rebuild it
idempotently first, so it always reflects the current data:

```
memories ──▶ entity extraction ──▶ relationship extraction ──▶ cross-meeting linking ──▶ graph
```

### Supported entities and relationships

Node types: `meeting`, `memory`, `person`, `project`, `customer`, `technology`,
`team`, `vendor`, `document`, and the memory primitives `decision`, `commitment`,
`risk`, `question`, `assumption`, `fact`.

Edge types: `mentions`, `assigned_to`, `relates_to`, `depends_on`, `supersedes`,
`resolves`, `blocks`, `supports`, `references`, `discussed_in`, `owned_by`,
`connected_to`.

Entities are global nodes keyed by a slug, so a project (or customer, technology,
…) repeated across meetings is the *same* node — that is what links meetings over
time and answers "which meetings discussed Project Atlas?".

### Graph traversal

```bash
meeting-memory graph --db atlas.db                       # summary counts
meeting-memory neighbors project:atlas --db atlas.db --type meeting
meeting-memory path person:lena project:atlas --db atlas.db
```

```text
node: project:atlas  [project]  Atlas
neighbors (3):
  meeting:meeting1  [meeting]  Project Atlas Kickoff
  meeting:meeting2  [meeting]  Project Atlas Weekly Sync
  meeting:meeting3  [meeting]  Project Atlas Beta Review
```

The library exposes `neighbors`, `incoming`, `outgoing`, `related`,
`related_memories`/`related_meetings`/`related_people`/`related_projects`,
`find_path`, and `connected_components`, plus `decision_lineage`/`risk_lineage`
that order a `SUPERSEDES`/`CONNECTED_TO` chain oldest-to-newest. Every traversal
explores neighbours in a fixed sorted order, so output is reproducible.

### Graph exports

```bash
meeting-memory export-graph --db atlas.db --format json
meeting-memory export-graph --db atlas.db --format mermaid --type meeting,project
meeting-memory export-graph --db atlas.db --format dot > atlas.dot
```

All three formats include node and edge labels and emit nodes/edges in sorted
order for stable, diff-friendly output.

### Library

```python
from meeting_memory.graph import GraphEngine, SQLiteGraphStore, build_graph
from meeting_memory.storage import SQLiteMemoryStore

with SQLiteMemoryStore("atlas.db") as memory_store:
    graph_store = SQLiteGraphStore("atlas.db")
    build_graph(memory_store, graph_store)        # idempotent

engine = GraphEngine(graph_store)
for meeting in engine.related_meetings("project:atlas"):
    print(meeting.label)
graph_store.close()
```

### Limitations

- Entity extraction is **vocabulary- and rule-based** — projects/customers via
  patterns like "Project X", technologies via a built-in lexicon, and any
  configurable vocabulary. Unlisted entities phrased differently are not found.
- Semantic edges (`resolves`, question/assumption ↔ decision) are derived from
  **shared entities**, not meaning, so they are precise but not exhaustive.
- Like the store, the graph is single-file SQLite for local/CLI use.

See [`docs/graph.md`](docs/graph.md) for the architecture, schema, entity and
relationship extraction rules, traversal, lineage, and future graph-reasoning
extensions. Runnable graph examples live in [`examples/graph/`](examples/graph/).

## Decision intelligence & organizational insights (Phase 6)

Phase 6 turns the stored memory and graph into deterministic organizational
intelligence. A small **plugin architecture** discovers four kinds of provider —
insight, metric, recommendation, and report — and the engine runs every provider
that supports the analysed context, in a fixed (name-sorted) order.

```bash
# Discover insights across all meetings (recurring risks, commitment overload, ...)
meeting-memory insights --db atlas.db

# Organizational-health metrics
meeting-memory metrics --db atlas.db

# Evidence-backed recommendations, highest priority first
meeting-memory recommendations --db atlas.db

# Full report as Markdown (also: text, json), optionally written to a file
meeting-memory report --db atlas.db --format markdown --output report.md

# Every command accepts --project, --person, and --meeting filters; insights and
# recommendations also take --type / --limit, and report takes --format / --output.
meeting-memory insights --db atlas.db --person Alice --type recurring_risk --json
```

### What it computes

- **Decision intelligence** — repeatedly superseded decisions, revisited
  decisions, long-running lineages, and decision density/velocity/stability.
- **Commitment intelligence** — open/resolved counts, resolution rate, overdue
  and aging commitments, per-owner workload, and commitment overload.
- **Risk intelligence** — recurring, unresolved, and long-lived risks, plus
  project risk hotspots and recurring blockers (via the graph).
- **Organizational health** — a composite score over decision stability,
  commitment completion, risk resolution, meeting productivity, knowledge reuse,
  and cross-team collaboration, with average resolution time and risk density.
- **Recommendations** — each insight maps to a prioritised, severity-tagged
  recommendation carrying its supporting evidence and related memories.

A deterministic **reference date** (the latest meeting date) replaces wall-clock
time, so overdue/aging/age analyses are fully reproducible.

### Limitations

- Insights are **rule- and threshold-based**, computed from stored memory and the
  graph — there is no inference or prediction.
- Recommendations are a fixed mapping from insight type to advice; they prioritise
  and surface evidence, they do not author novel guidance.
- Health scores use fixed, documented formulas and weights.

See [`docs/intelligence.md`](docs/intelligence.md) for the provider architecture,
metric and insight definitions, recommendation rules, report generation, and
future ML extension points. Runnable examples live in
[`examples/intelligence/`](examples/intelligence/).

## Connector framework & automation (Phase 7)

Phase 7 wraps the whole pipeline in a deterministic **connector framework** so
meeting data can be imported from many sources and organizational intelligence
exported to many destinations, with declarative pipelines that chain the steps
together. Like every earlier phase it is standard-library only: no LLM APIs, no
external schedulers, no network access, and no credentials.

```bash
# Import every supported transcript in a directory (txt/json/markdown/csv)
meeting-memory import-dir examples/history --db atlas.db --recursive

# Preview an import without writing (dry-run), as JSON
meeting-memory import-dir examples/history --db atlas.db --dry-run --json

# Export organizational data in a chosen format (markdown/json/html/csv/graph/summaries)
meeting-memory export --db atlas.db --format markdown --output report.md

# Run a declarative pipeline (import -> graph -> intelligence -> export)
meeting-memory automate examples/pipelines/daily.yaml --db atlas.db
meeting-memory automate examples/pipelines/daily.yaml --dry-run

# Inspect recorded runs and machine-readable logs
meeting-memory jobs --db atlas.db
meeting-memory logs --db atlas.db --limit 20

# Simulate a schedule (no daemon): show the next run times
meeting-memory schedule examples/pipelines/weekly.yaml --count 5
```

### What it provides

- **Connector interfaces** — `ImportConnector`, `ExportConnector`, and
  `AutomationConnector` all expose `metadata()`, `validate()`, `supports()`,
  `execute()`, and `dry_run()`, discovered through a `ConnectorRegistry` and
  driven by a `ConnectorManager` facade.
- **Import connectors** — plain-text, JSON, Markdown, and CSV transcripts, plus
  directory, recursive-directory, batch (explicit file list), and zip-archive
  importers. Every importer reuses the existing parser and extraction pipeline
  and reports per-file outcomes (imported / skipped-duplicate / failed).
- **Export connectors** — JSON, Markdown, HTML, CSV, graph (JSON/Mermaid/DOT),
  intelligence reports, and per-meeting summaries, written to a file or stdout.
- **Automation engine** — an `AutomationEngine`/`JobRunner`/`PipelineExecutor`
  runs `import → graph → intelligence → export` over a shared `ExecutionContext`,
  with status aggregation and a `JobHistory` recorded beside the database.
- **Scheduler** — deterministic `once`/`hourly`/`daily`/`weekly`/`manual`
  frequencies and a five-field `cron` subset (ranges, steps, lists), with a
  `simulate(...)` mode and no background daemon.
- **Structured logging** — every stage emits a machine-readable record (stage,
  connector, duration, items, warnings, errors, destination, correlation id) to
  a JSON Lines sink, queryable through `meeting-memory logs`.
- **Pipeline configuration** — declarative YAML or JSON pipelines, parsed by a
  dependency-free YAML-subset reader and validated before execution.

```yaml
# examples/pipelines/daily.yaml
name: daily-intelligence
schedule:
  frequency: daily
steps:
  - type: import
    source: examples/history
    recursive: true
  - type: graph
  - type: intelligence
  - type: export
    format: markdown
    output: out/daily-report.md
```

### Limitations

- Connectors are **deterministic and local**: the bundled set reads files and
  writes reports — live SaaS sources (Slack, Zoom, Notion, Jira, GitHub) are
  designed to plug into the same interfaces but are not implemented here.
- The scheduler **computes** run times; it does not run a daemon. Trigger
  `automate` from an external timer (cron/systemd) using the simulated times.
- The YAML reader supports the **subset** needed for pipelines (block mappings
  and sequences, scalars, comments), not the full YAML specification.

See [`docs/connectors.md`](docs/connectors.md) for the connector interfaces,
pipeline execution model, automation architecture, scheduler, configuration
schema, and future SaaS connector extensions. Runnable examples live in
[`examples/pipelines/`](examples/pipelines/).

## REST API, Python SDK & web dashboard (Phase 8)

Phase 8 turns the system into a reusable platform. Every capability is exposed
through one shared **service layer** (`MeetingService`, `MemoryService`,
`RetrievalService`, `GraphService`, `IntelligenceService`, `AutomationService`,
`ExportService`) that the CLI, REST API, SDK, and dashboard all call — no
duplicated logic.

```bash
# Serve the API (Swagger UI at /docs, ReDoc at /redoc, dashboard at /dashboard)
python examples/api/serve.py --db atlas.db --port 8000

# Or with uvicorn directly (uses the MEETING_MEMORY_DB env var for the database)
MEETING_MEMORY_DB=atlas.db uvicorn meeting_memory.api.app:app --port 8000
```

Key endpoints: `GET /health`, `GET /version`, `POST /meetings/import`,
`GET /meetings`, `GET /meetings/{id}`, `GET /memories`, `GET /memories/{id}`,
`GET /search`, `GET /graph`, `GET /graph/neighbors`, `GET /graph/path`,
`GET /insights`, `GET /metrics`, `GET /recommendations`, `GET /reports`, and
`POST /automation/run` (plus `/automation/jobs` and `/automation/logs`). Every
response is typed; failures return a structured `ErrorResponse` with a
correlation id, and each response carries `X-Correlation-ID`, `X-API-Version`,
and `X-Process-Time-Ms` headers.

The **Python SDK** offers one method per capability with two interchangeable
transports — a local in-process mode and an HTTP mode — that share the same
surface:

```python
from meeting_memory.sdk import MeetingMemoryClient

# Local (in-process, no server) — runs the same routers and services
with MeetingMemoryClient.local("atlas.db") as client:
    client.import_directory("examples/history", recursive=True)
    hits = client.search("postgres")
    report = client.report(fmt="markdown")

# HTTP (against a running server) — identical method surface
with MeetingMemoryClient.connect("http://127.0.0.1:8000") as client:
    insights = client.insights()
```

The **dashboard** is a lightweight, server-rendered UI (no build step, no auth)
with Overview, Meetings, Search, Graph, Insights, Reports, and Jobs pages at
`/dashboard`. See [`docs/api.md`](docs/api.md), [`docs/sdk.md`](docs/sdk.md),
[`docs/dashboard.md`](docs/dashboard.md), and the runnable
[`examples/api/`](examples/api/) scripts.

## Performance, observability, deployment & recovery (Phase 9)

Phase 9 prepares the system for production without adding user-facing features.
Everything stays deterministic, dependency-free, and backward compatible.

- **Benchmark datasets** — seeded `small`/`medium`/`large`/`enterprise`
  generators with multiple projects and people, recurring risks, evolving
  decisions, long timelines, cross-meeting references, and thousands of memories.
- **Replay engine** — reconstruct and replay the meeting timeline (all, by
  project, by person, by date, or range) with step-by-step control and a speed
  multiplier.
- **Performance benchmarks** — measure import throughput, retrieval latency,
  graph construction, intelligence generation, report rendering, API/SDK latency,
  database size, and peak memory, producing JSON or text reports.
- **Observability** — counters, gauges, histograms, and timers via a
  `MetricsCollector`, plus `HealthSnapshot` and `SystemMetrics`, exported to JSON
  and Prometheus text format (no `prometheus_client` dependency).
- **Profiling** — CPU/memory profiling, pipeline stage timing, hot-path timing,
  and slow-query detection built on `cProfile`/`tracemalloc`.
- **Backup & recovery** — checksummed physical SQLite backups and portable,
  checksummed logical snapshots, both validated via `PRAGMA integrity_check`.
- **Deployment** — a multi-stage `Dockerfile`, `docker-compose.yml`, a
  production Compose example, a health-check probe, a volume for the database,
  environment-driven configuration, and a production startup script.

```bash
meeting-memory benchmark --dataset medium --iterations 3
meeting-memory replay --db atlas.db --timeline
meeting-memory metrics --db atlas.db --format prometheus
meeting-memory backup  --db atlas.db -o atlas.bak
meeting-memory restore --db restored.db atlas.bak
meeting-memory profile --db atlas.db --operation intelligence

# Container deployment
docker build -t meeting-memory:latest .
docker compose up -d
curl localhost:8000/health
```

See [`docs/performance.md`](docs/performance.md),
[`docs/deployment.md`](docs/deployment.md), [`docs/replay.md`](docs/replay.md),
and [`docs/backup.md`](docs/backup.md), plus the runnable
[`examples/ops/`](examples/ops/) scripts.

## Architecture overview

The package follows a clean, layered structure under `src/meeting_memory/`:

```
meeting_memory/
├── models/        # Typed domain models (Meeting, Speaker, Utterance, ...)
├── io/            # Transcript loading from disk (extensible format registry)
├── parser/        # Parsing raw content into meetings, plus validation
├── extraction/    # Phase 2: memory models, extractors, pipeline, dedup, validation
│   └── extractors/  # One rule-based extractor per memory type
├── storage/       # Phase 3: SQLite store, registry, importer, lifecycle, dedup
├── retrieval/     # Phase 4: planner, engine, ranking, context, explanations
├── graph/         # Phase 5: models, store, entity/relationship extraction,
│                  #          cross-meeting linking, traversal, lineage, export
├── intelligence/  # Phase 6: models, context, providers/registry, engine,
│                  #          decision/commitment/risk/health, recommendations, report
├── connectors/    # Phase 7: models, logging, base/registry/manager, importers,
│                  #          exporters, scheduler, config, automation engine
├── services/      # Phase 8: shared service layer wrapping every capability
├── api/           # Phase 8: FastAPI app, routers, schemas, dependencies,
│                  #          middleware, errors, version, and the dashboard
├── sdk/           # Phase 8: MeetingMemoryClient (local + HTTP transports)
├── benchmarks/    # Phase 9: deterministic datasets + performance benchmark runner
├── replay/        # Phase 9: timeline reconstruction and replay sessions
├── observability/ # Phase 9: metrics (JSON/Prometheus) + profiling utilities
├── recovery/      # Phase 9: physical backups and logical snapshots
├── utils/         # Normalization and statistics helpers
├── exceptions/    # Exception hierarchy rooted at MeetingMemoryError
└── cli.py         # Command-line entry point (service-backed; parse/.../profile)
```

Deployment artifacts live at the repository root: `Dockerfile`,
`docker-compose.yml`, `.dockerignore`, and `scripts/` (production startup and
health-check probe).

Data flows in one direction:

```
file ──▶ io.load_transcript ──▶ RawTranscript ──▶ parser.parse ──▶ Meeting
                                                          │
                                       utils.normalize_* ─┘
Meeting ──▶ parser.validate_meeting          (semantic checks)
Meeting ──▶ utils.compute_statistics         (descriptive metrics)
Meeting ──▶ extraction.extract_memories ──▶ ExtractionResult
              (scan ▶ extractors ▶ dedup ▶ validate ▶ filter)
ExtractionResult ──▶ storage.persist_extraction ──▶ SQLiteMemoryStore
              (meeting registry + memories + evidence + metadata)
SQLiteMemoryStore ──▶ query / lifecycle ──▶ StoredMemory records
RetrievalQuery ──▶ retrieval.MemoryRetriever ──▶ RetrievalResult
              (plan ▶ filter ▶ rank ▶ order ▶ context + explain)
SQLiteMemoryStore ──▶ graph.build_graph ──▶ SQLiteGraphStore (nodes + edges)
              (entities ▶ relationships ▶ cross-meeting linking)
SQLiteGraphStore ──▶ graph.GraphEngine ──▶ neighbors / paths / lineage / export
SQLiteMemoryStore (+ graph) ──▶ intelligence.IntelligenceEngine ──▶ InsightReport
              (context ▶ providers ▶ insights + metrics + recommendations ▶ render)
sources ──▶ connectors.import ──▶ (parser ▶ extraction ▶ storage)
              (text/json/markdown/csv, directory/recursive/batch/zip)
AutomationJob ──▶ connectors.AutomationEngine ──▶ AutomationResult + JobHistory
              (import ▶ graph ▶ intelligence ▶ export, with structured logs)
SQLiteMemoryStore (+ graph) ──▶ connectors.export ──▶ file / stdout
              (json/markdown/html/csv/graph/summaries)
services.* ──▶ wrap every layer above into one orchestration surface
CLI / api (FastAPI) / sdk (MeetingMemoryClient) / dashboard ──▶ services.*
              (one shared implementation; deterministic, SQLite-backed)
benchmarks.generate_dataset ──▶ seeded transcripts ──▶ benchmarks.run_benchmarks
              (import / retrieval / graph / intelligence / report timings)
SQLiteMemoryStore ──▶ replay.ReplayEngine ──▶ ReplayTimeline / ReplaySession
SQLiteMemoryStore ──▶ recovery.backup / export_snapshot ──▶ checksummed artifacts
observability.MetricsCollector ──▶ JSON / Prometheus exposition
```

- **Loading is decoupled from parsing.** The loader only reads and decodes a
  file; the parser interprets the decoded content. Adding a new format means
  registering a reader callable — no parser changes required.
- **Extraction is decoupled from parsing.** Extractors consume a `Meeting` and
  emit `ExtractedMemory` records; the registry is open for extension (add an
  extractor without touching the pipeline).
- **Models are immutable.** All domain models are frozen dataclasses, so a parsed
  `Meeting` and every `ExtractedMemory` is a stable, hashable value object.
- **Errors are specific.** Every failure raises a descriptive subclass of
  `MeetingMemoryError`, distinguishing load, parse, validation, and extraction
  problems.

## Development

```bash
ruff check .          # lint
ruff format --check . # formatting check
mypy src              # strict type checking
pytest --cov          # run tests with coverage
python -m build       # build the wheel/sdist
docker build .        # build the container image
docker compose config # validate the Compose file

# Run the API locally and browse the docs/dashboard
python examples/api/serve.py --db atlas.db --port 8000
```

## License

Released under the [MIT License](LICENSE).

## Citation

If you use this project in academic work, please cite it — see [CITATION.cff](CITATION.cff).
