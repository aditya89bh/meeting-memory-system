# Tutorial 3 — Searching memory

Once transcripts are imported you can run ranked retrieval over everything the system
remembers. This tutorial covers querying, filtering, and explaining results.

## Setup

```bash
meeting-memory import-dir examples/organizations/enterprise --db orion.db --recursive
```

## Basic search

```bash
meeting-memory search "migrate core services" --db orion.db
```

Results are scored and ordered by relevance. Each row shows the score, memory type,
speaker, and text.

## Filter the search

```bash
# Limit the number of results
meeting-memory search "risk" --db orion.db --limit 5

# Restrict to specific memory types
meeting-memory search "data residency" --db orion.db --type risk

# Restrict to a speaker
meeting-memory search "rollback" --db orion.db --speaker Diego
```

> Retrieval uses AND semantics across query terms — a memory must contain every term to
> match. Search for `risk` rather than `recurring risk` if a phrase returns nothing.

## Explain a result

To understand *why* a result ranked where it did:

```bash
meeting-memory explain "migration" --db orion.db
```

This shows the query plan and the scoring factors behind each ranked memory.

## Browse a timeline

To see memories for a meeting or topic in chronological order:

```bash
meeting-memory timeline --db orion.db
```

## From the API or SDK

The same retrieval is available over HTTP (`GET /search`) and through the SDK
(`client.search(...)`). See the [REST API](rest-api.md) and [Python SDK](python-sdk.md)
tutorials.

Next: [Using the graph](using-the-graph.md).
