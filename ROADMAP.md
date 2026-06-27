# Roadmap

The Meeting Memory System reached **v1.0.0** with a complete, deterministic pipeline from
transcripts to organizational intelligence, exposed through a CLI, REST API, Python SDK,
and dashboard, plus production operations (benchmarks, observability, backup/recovery,
Docker).

This roadmap describes possible future directions. **A core constraint remains: the
system stays deterministic, local-first, and free of LLM/embedding dependencies.** Any
feature that would compromise reproducibility is explicitly out of scope for the core.

## Guiding principles

- Determinism and explainability over generative convenience.
- Local-first: no required external services.
- Backward compatibility: additive schema migrations, stable public APIs.

## Candidate areas (post-1.0)

### Ingestion
- More transcript formats and connector adapters (kept offline and deterministic).
- Richer speaker/diarization metadata handling.

### Extraction & analysis
- Additional rule-based memory types and insight providers via the existing plugin points.
- Configurable extraction vocabularies per organization.

### Graph & retrieval
- More graph relationship types and lineage queries.
- Saved queries and query templates.

### Interfaces
- Dashboard enhancements (filtering, saved views).
- SDK convenience helpers and typed result models.

### Operations
- Additional export targets for metrics and reports.
- More backup backends behind the existing recovery interfaces.

### Optional, clearly-separated integrations
- An *optional* plugin boundary for users who explicitly want to add their own
  (potentially non-deterministic) enrichment — never enabled by default and never part
  of the deterministic core.

## Out of scope for the core

- Built-in LLM summarization or generation.
- Embeddings / vector search as a required dependency.
- Any feature that makes identical inputs produce non-identical outputs.

Have an idea? Open a [feature request](https://github.com/aditya89bh/meeting-memory-system/issues/new/choose).
