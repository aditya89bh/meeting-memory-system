# Meeting Memory System

**Turn raw meeting transcripts into durable, queryable institutional memory** — then
search it, graph it, and mine it for insights. The system extracts the *memory
primitives* of every meeting (decisions, commitments, open loops, risks, assumptions,
questions, and facts) and connects them across meetings.

It is **100% deterministic and local-first**: no LLM APIs, no embeddings, no vector
database, no network calls. The same transcripts always produce the same memory, graph,
and reports.

## See it in 60 seconds

```bash
pip install -e .
meeting-memory demo
```

## Where to go next

- **New here?** Start with the [Getting started tutorial](tutorials/getting-started.md).
- **Prefer notebooks?** See the [runnable notebooks](https://github.com/aditya89bh/meeting-memory-system/tree/main/notebooks).
- **Want the big picture?** Read the [architecture](architecture.md) and
  [database schema](schema.md).
- **Evaluating?** Browse the [case studies](case-studies/) and
  [example organizations](https://github.com/aditya89bh/meeting-memory-system/tree/main/examples/organizations).
- **Deploying?** Follow the [deployment guide](deployment.md) and
  [production tutorial](tutorials/production-deployment.md).

## Reference

- [CLI reference](cli.md)
- [REST API](api.md)
- [Python SDK](sdk.md)
- [Performance & benchmarks](performance.md) · [Benchmark charts](benchmarks.md)
