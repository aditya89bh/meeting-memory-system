# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-06-28

First stable release. Phase 10 focuses on productization, documentation, and release
readiness — no new core functionality and no public API changes.

### Added

- `meeting-memory demo` — a guided, end-to-end demonstration that imports example
  meetings, builds memory, searches, builds the graph, generates intelligence, and
  renders a report in under a minute.
- Five complete [example organizations](examples/organizations/) (startup, growing SaaS,
  enterprise engineering, research lab, university), each demonstrating decision
  evolution, recurring risks, commitments, an organizational graph, and reports.
- Dependency-free benchmark visualizations (`meeting_memory.benchmarks.visualize`) and a
  `meeting-memory benchmark --charts DIR` option, plus rendered SVG assets.
- Architecture and database-schema diagrams ([docs/architecture.md](docs/architecture.md),
  [docs/schema.md](docs/schema.md)).
- Step-by-step [tutorials](docs/tutorials/) and runnable [Jupyter notebooks](notebooks/)
  covering import, search, graph, intelligence, SDK, API, and deployment.
- [Case studies](docs/case-studies/) for recurring risks, decision reversals, knowledge
  reuse, engineering organizations, startup operations, and customer support.
- Open-source community files: `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, `ROADMAP.md`, `CITATION.cff`, issue/PR templates.
- MkDocs documentation site configuration and a CI/release GitHub Actions workflow.

### Changed

- Rewrote the README into a product-focused overview with a quickstart, feature
  summary, and documentation map.
- Updated project URLs and metadata in `pyproject.toml`.

## [0.9.0] - 2026-06-27

### Added

- **Phase 9 — Performance, observability, deployment & production validation.**
  Deterministic benchmark datasets and a benchmark runner; a read-only replay engine;
  a dependency-free observability layer (metrics, health, Prometheus export); CPU/memory
  profiling utilities; physical backup/restore and logical snapshots; Docker deployment
  artifacts; and `benchmark`, `replay`, `metrics`, `backup`, `restore`, and `profile`
  CLI commands.

## [0.8.0] - 2026-06-27

### Added

- **Phase 8 — REST API, Python SDK & web dashboard.** A FastAPI application exposing the
  full capability set, a `MeetingMemoryClient` with interchangeable local/HTTP
  transports, and a server-rendered web dashboard, all over a shared service layer.

## [0.7.0]

### Added

- **Phase 7 — Connector framework & automation.** Pluggable transcript importers and
  exporters, declarative pipelines, scheduling simulation, and job/log auditing.

## [0.6.0]

### Added

- **Phase 6 — Organizational intelligence.** Deterministic insight, metric,
  recommendation, and report providers over stored memory and the graph.

## [0.5.0]

### Added

- **Phase 5 — Organizational graph.** A typed, directed graph linking meetings, people,
  projects, decisions, risks, and commitments, with traversal and export.

## [0.4.0]

### Added

- **Phase 4 — Retrieval.** A query planner, AND-semantics retrieval engine, transparent
  ranking, context assembly, and per-match explanations.

## [0.3.0]

### Added

- **Phase 3 — Persistence.** A deterministic SQLite memory store with migrations.

## [0.2.0]

### Added

- **Phase 2 — Extraction.** Rule-based extraction of typed memory primitives.

## [0.1.0]

### Added

- **Phase 1 — Parsing.** Transcript parsing into a normalized, typed `Meeting` model.

[Unreleased]: https://github.com/aditya89bh/meeting-memory-system/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/aditya89bh/meeting-memory-system/releases/tag/v1.0.0
[0.9.0]: https://github.com/aditya89bh/meeting-memory-system/releases/tag/v0.9.0
[0.8.0]: https://github.com/aditya89bh/meeting-memory-system/releases/tag/v0.8.0
