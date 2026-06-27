# Organizational Intelligence Engine (Phase 6)

Phase 6 mines the organizational memory built by Phases 1–5 for deterministic
patterns and turns them into metrics, insights, recommendations, and reports. It
answers questions such as:

- Which decisions repeatedly change?
- Which risks never get resolved?
- Which people accumulate unfinished commitments?
- Which projects repeatedly appear with blockers?
- Which discussions happen over and over?

Like every earlier phase it is **deterministic and standard-library only**: no
LLM APIs, no embeddings, no external analytics engines, and no external
databases. Every number is computed from stored memory and the graph; nothing is
inferred or fabricated.

## Where it sits in the pipeline

```
Parser ─▶ Extraction ─▶ Storage ─▶ Retrieval ─▶ Graph ─▶ Intelligence
```

The intelligence engine reads the `SQLiteMemoryStore` (and, when available, the
`SQLiteGraphStore`), builds a single immutable analysis context, and runs the
discovered providers against it.

## Provider architecture

Every analysis is a small **provider** implementing one of four interfaces
(`src/meeting_memory/intelligence/providers.py`). Each provider exposes:

- `metadata()` → a `ProviderMetadata` (name, version, category, description),
- `supports(context)` → whether it can run against this context (default `True`),
- `analyze(...)` → the analysis itself.

| Interface | `analyze` signature | Produces |
| --- | --- | --- |
| `InsightProvider` | `analyze(context)` | `list[Insight]` |
| `MetricProvider` | `analyze(context)` | a metrics value object |
| `RecommendationProvider` | `analyze(context, insights)` | `list[Recommendation]` |
| `ReportProvider` | `analyze(report)` (+ `fmt()`) | a rendered `str` |

Providers register themselves at import time via the registry
(`registry.py`). `default_providers()` imports the domain modules, collects the
registered providers, and returns them name-sorted so discovery and execution are
deterministic. The `IntelligenceEngine` (`engine.py`) orchestrates everything:

```python
from meeting_memory.intelligence import IntelligenceEngine
from meeting_memory.graph import SQLiteGraphStore
from meeting_memory.storage import SQLiteMemoryStore

with SQLiteMemoryStore("atlas.db") as store:
    graph = SQLiteGraphStore("atlas.db")
    report = IntelligenceEngine().analyze(store, graph)   # builds the graph, then analyses
    print(report.health.overall)
    graph.close()
```

The engine is reusable in future phases: add a provider, register it, and it is
discovered automatically — no engine changes required.

## Analysis context

`AnalysisContext` (`context.py`) is a frozen, pre-filtered view of memory shared
by every provider, so analyses never touch the database directly. It holds the
selected memories and meetings, the attached graph, the active filters, and a
deterministic **reference date** — the latest meeting date by default — that
replaces wall-clock time so overdue/aging/age calculations are reproducible.

`AnalysisFilters` narrows the slice by `project` (resolved through the graph),
`person` (commitment owner or speaker), `meeting` ids, and memory types. Deleted
memories are always excluded.

## Metrics

Metric providers compute immutable value objects (`models.py`):

- **`DecisionMetrics`** — total, active, superseded, revisited, stability
  (active/total), density (per meeting), velocity (per week), distinct owners,
  top owner.
- **`CommitmentMetrics`** — total, open, resolved, overdue, resolution rate,
  average open age, top owner and their open count.
- **`RiskMetrics`** — total, open, resolved, resolution rate, recurring count,
  max recurrence, density, and hotspot project (from the graph).
- **`MeetingMetrics`** — meeting/memory counts, average memories per meeting,
  productivity (decisions + commitments per meeting), repeated-discussion rate,
  and span in days.
- **`ProjectMetrics`/`PersonMetrics`** — per-project risk/decision/meeting/blocker
  counts (from the graph) and per-person commitment/decision/attendance counts.

### Organizational health

`OrganizationalHealth` composes the four scalar metric blocks plus context-level
signals into a `scores` dictionary and an `overall` number (the mean of the
normalised sub-scores):

| Score | Definition |
| --- | --- |
| `decision_stability` | active / total decisions |
| `commitment_completion` | resolved / total commitments |
| `risk_resolution` | resolved / total risks |
| `meeting_productivity` | productivity capped at a target of 3.0 |
| `knowledge_reuse` | fraction of memories whose content recurs across meetings |
| `cross_team_collaboration` | fraction of participants who share a meeting |
| `repeated_discussion_rate` | fraction of content groups that recur (informational) |
| `risk_density` | risks per meeting (informational) |
| `avg_resolution_days` | mean created→resolved span for resolved/archived memories |

The first six feed `overall`; the rest are informational.

## Insights

Insight providers emit `Insight` records (type, category, severity, title,
detail, metric, subjects, and `InsightEvidence`). Severity scales with the
underlying count via fixed thresholds.

- **Decision** (`decision.py`) — `repeatedly_superseded_decision` (supersession
  chains via `superseded_by`), `revisited_decision` (same content across
  meetings), `long_running_decision` (lineage span), `unstable_decisions`
  (low stability over enough decisions).
- **Commitment** (`commitment.py`) — `open_commitment_overload` (per owner),
  `overdue_commitment` (past `due` vs reference date), `aging_commitment` (old
  and not overdue), `low_commitment_resolution`.
- **Risk** (`risk.py`) — `recurring_risk`, `long_lived_risk`, `unresolved_risk`,
  and the graph-derived `risk_hotspot` and `project_blocker`.

## Recommendation rules

`recommendations.py` maps each insight onto a prioritised, evidence-backed
`Recommendation` using a fixed table of (title, advice) per insight type.
Priority is derived from severity (`critical→urgent`, `high→high`, …), the
category is carried over, and the insight's evidence and related memory ids are
attached. A separate rule flags an ineffective meeting cadence when productivity
is low across enough meetings. Insight types that no provider currently emits are
intentionally left unmapped, so every recommendation traces back to a real
analysis.

## Report generation

`report.py` renders a finished `InsightReport` into three formats via report
providers — **JSON**, **Markdown**, and **plain text** — all sharing the same
sections: executive summary, organizational health, decision insights, commitment
insights, risk insights, recommendations, and an appendix of per-project and
per-person metrics. Rendering is byte-for-byte reproducible.

## CLI

```bash
meeting-memory insights        --db atlas.db [--project P] [--person N] [--meeting IDS] [--type T,...] [--limit N] [--json]
meeting-memory metrics         --db atlas.db [--project P] [--person N] [--meeting IDS] [--json]
meeting-memory recommendations --db atlas.db [--project P] [--person N] [--meeting IDS] [--limit N] [--json]
meeting-memory report          --db atlas.db [--format json|markdown|text] [--output FILE] [filters]
```

## Future ML extension points

The engine is deliberately structured so that statistical or ML-based analyses
could be added later **without** changing the orchestration or the existing
deterministic providers:

- **New providers.** Implement `InsightProvider`/`MetricProvider`/… and register
  it; the engine discovers it automatically. An ML model could back a provider's
  `analyze` while keeping the same typed inputs and outputs.
- **`supports()` gating.** A provider can opt in only when its prerequisites
  (e.g. enough history, or an optional model) are present, leaving the
  deterministic baseline untouched otherwise.
- **Context enrichment.** `AnalysisContext` is the single hand-off point; richer
  features (embeddings, external signals) could be attached there behind a flag
  without rewriting providers.
- **Stable contracts.** Because models are immutable and JSON-serialisable, any
  future scoring can be compared against the deterministic baseline and reported
  through the same `InsightReport`.
