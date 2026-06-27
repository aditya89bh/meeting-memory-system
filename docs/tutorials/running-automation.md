# Tutorial 6 — Running automation

Automation pipelines let you import new transcripts and refresh analysis on a schedule,
with a full audit trail of every run.

## Run a pipeline once

The `automate` command takes a pipeline configuration file as its argument:

```bash
meeting-memory automate examples/pipelines/daily.yaml --db atlas.db
```

A pipeline describes a source of transcripts and the actions to run (import, then
refresh graph/intelligence, then export). See the bundled
[`examples/pipelines/`](../../examples/pipelines/) for ready-to-edit definitions
(`daily.yaml`, `weekly.yaml`, `batch.json`).

## Dry run first

Preview what a pipeline would do without writing anything:

```bash
meeting-memory automate examples/pipelines/daily.yaml --db atlas.db --dry-run
```

## Inspect job history

Every run is recorded:

```bash
meeting-memory jobs --db atlas.db          # list job runs
meeting-memory logs --db atlas.db          # recent structured log lines
```

## Preview the schedule

The pipeline config carries its own schedule. To see the next run times without running
a daemon:

```bash
meeting-memory schedule examples/pipelines/daily.yaml --count 5
```

For real recurring execution, wire the `automate` command into cron or a container
scheduler; see the [Production deployment](production-deployment.md) tutorial.

Next: [REST API](rest-api.md).
