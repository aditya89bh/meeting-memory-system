# Release notes

## v1.0.0 — First stable release

The Meeting Memory System turns raw meeting transcripts into durable, queryable
institutional memory — then lets you search it, graph it, and mine it for insights. It
is **100% deterministic and local-first**: no LLM APIs, no embeddings, no vector
database, and no network calls. The same transcripts always produce the same memory,
graph, and reports.

v1.0.0 is a productization and documentation milestone. It adds no new core
functionality and makes no breaking changes to the public CLI, REST API, or Python SDK.

### Highlights

- **60-second demo.** `meeting-memory demo` imports example meetings, builds memory,
  searches, builds the graph, generates intelligence, and renders a report end to end in
  under a minute.
- **Five example organizations.** Startup, growing SaaS, enterprise engineering,
  research lab, and university datasets — each demonstrating decision evolution,
  recurring risks, commitments, an organizational graph, and reports.
- **Complete documentation set.** Ten step-by-step tutorials, seven runnable Jupyter
  notebooks, six case studies, architecture and database-schema diagrams, and a
  searchable MkDocs Material site.
- **Benchmark visualizations.** Dependency-free SVG charts for import throughput,
  retrieval latency, graph and intelligence generation, memory usage, and database
  growth, generated directly from benchmark data.
- **Production operations in the box.** Benchmarks, observability (metrics, health,
  Prometheus export), CPU/memory profiling, physical backup/restore, logical snapshots,
  a deterministic replay engine, and Docker deployment.
- **Four surfaces, one behaviour.** A shared service layer powers the CLI, REST API,
  Python SDK, and web dashboard with identical, deterministic results.
- **Release automation.** GitHub Actions for CI (lint, type check, tests across
  Python 3.10–3.12, build, demo smoke test), documentation publishing, and tagged
  releases.

### Quality

- 100% test coverage across the suite.
- `ruff`, `ruff format`, and `mypy --strict` clean.
- Reproducible builds (`python -m build`) with a strict MkDocs site build.

### Known limitations

- **Deterministic by design.** Extraction and analysis are rule-based, not generative.
  This is intentional — it is *not* a meeting summarizer and will not paraphrase or
  infer beyond its rules.
- **English-oriented heuristics.** The extraction vocabularies are tuned for English
  transcripts; other languages may need custom vocabularies.
- **SQLite storage.** The default store is single-node SQLite, suited to single-instance
  deployments. Horizontal scale-out is out of scope for the core.
- **Docker image not validated in this environment.** The `Dockerfile` and Compose
  files are provided and structurally tested; the image build was not run here because
  Docker was unavailable. The CI/release workflows exercise the rest of the gates.

### Migration

Upgrading from 0.9.0 requires **no action** — there are no API or schema changes. See
[`MIGRATION.md`](MIGRATION.md) for details and general upgrade guidance.

### Future roadmap

Post-1.0 directions are tracked in [`ROADMAP.md`](ROADMAP.md). The core constraint
remains: the system stays deterministic, local-first, and free of LLM/embedding
dependencies. Candidate areas include more transcript formats and connectors, additional
rule-based memory types and insight providers, richer graph relationships, and saved
queries — all additive and backward compatible.

### Documentation

- Getting started: [`docs/tutorials/getting-started.md`](docs/tutorials/getting-started.md)
- Tutorials: [`docs/tutorials/`](docs/tutorials/)
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Case studies: [`docs/case-studies/`](docs/case-studies/)
- Full changelog: [`CHANGELOG.md`](CHANGELOG.md)
