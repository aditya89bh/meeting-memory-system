# Retrieval examples

These examples search the persistent memory built from the three Project Atlas
transcripts in [`examples/history`](../history). Import them into one database
first; the `--now` flag keeps timestamps reproducible so the output below is
stable.

```bash
meeting-memory import examples/history/meeting1.txt --db atlas.db --now 2026-03-01T00:00:00+00:00
meeting-memory import examples/history/meeting2.txt --db atlas.db --now 2026-03-01T00:00:00+00:00
meeting-memory import examples/history/meeting3.txt --db atlas.db --now 2026-03-01T00:00:00+00:00
```

## Decision history — why did we choose PostgreSQL?

```bash
meeting-memory search postgres --db atlas.db --type decision
```

```
meeting1:decision:1  (0.890)  2026-02-02  [decision] active  Priya: We decided to build Atlas on PostgreSQL for the first release.
  ✓ memory type decision
  ✓ keyword "postgres"
```

## Recurring risks — which risk keeps appearing?

The vendor API risk is raised in every weekly meeting. A timeline makes the
recurrence obvious, oldest first.

```bash
meeting-memory timeline --type risk --db atlas.db
```

```
2026-02-02  meeting1:risk:3  [risk] Marco: There is a risk that the vendor API rate limits will slow ingestion.
2026-02-09  meeting2:risk:2  [risk] Marco: There is a risk that the vendor API rate limits will slow ingestion.
2026-02-16  meeting3:risk:2  [risk] Marco: There is a risk that the vendor API rate limits will slow ingestion.
```

## Commitment tracking — what is still active?

```bash
meeting-memory search --type commitment --status active --db atlas.db
```

## Speaker search — what did Marco raise?

```bash
meeting-memory search --speaker Marco --db atlas.db
```

## Timeline search — everything between two dates

```bash
meeting-memory timeline --between 2026-02-01 2026-02-10 --db atlas.db
```

## Explain — why is this memory here?

```bash
meeting-memory explain meeting1:decision:1 --db atlas.db
```

```
matched because:
  ✓ speaker Priya
  ✓ memory type decision
  ✓ status active
context:
    [0] Priya: Welcome to the Project Atlas kickoff, let's set direction.
  > [1] Priya: We decided to build Atlas on PostgreSQL for the first release.
    [2] Marco: I will set up the staging environment by next Friday.
```

Every result is ranked deterministically and explained from the data alone — no
language model, embeddings, or external search engine is involved.
