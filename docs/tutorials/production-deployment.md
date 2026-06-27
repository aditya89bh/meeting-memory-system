# Tutorial 10 — Production deployment

This tutorial covers running the system reliably: configuration, persistence, backups,
observability, and recovery. For deeper references see
[`docs/deployment.md`](../deployment.md), [`docs/backup.md`](../backup.md), and
[`docs/performance.md`](../performance.md).

## 1. Provision storage

The entire state lives in one SQLite file. Put it on durable, backed-up storage and
point the app at it:

```bash
export MEETING_MEMORY_DB=/var/lib/meeting-memory/data.db
```

In containers, mount a volume at the data directory (see
[Docker deployment](docker-deployment.md)).

## 2. Run the API

```bash
MEETING_MEMORY_DB=$MEETING_MEMORY_DB \
MEETING_MEMORY_WORKERS=2 \
uvicorn meeting_memory.api.app:app --host 0.0.0.0 --port 8000
```

The provided `scripts/start.sh` wraps this and reads all settings from environment
variables, which is what the container image runs.

## 3. Wire up health checks

Point your orchestrator's liveness/readiness probe at `/health`, or run the bundled
probe:

```bash
python scripts/healthcheck.py
```

## 4. Schedule imports and analysis

Run automation pipelines on a schedule (cron, systemd timer, or a container scheduler):

```bash
meeting-memory automate /etc/meeting-memory/daily.yaml --db "$MEETING_MEMORY_DB"
```

Audit runs with `meeting-memory jobs` and `meeting-memory logs`.

## 5. Back up and recover

Take consistent physical backups using SQLite's online backup API:

```bash
meeting-memory backup --db "$MEETING_MEMORY_DB" -o /backups/$(date +%F).db
```

Restore from a backup (the backup path is the positional argument):

```bash
meeting-memory restore /backups/2026-03-01.db --db "$MEETING_MEMORY_DB"
```

For portable, checksummed logical snapshots, see [`docs/backup.md`](../backup.md).

## 6. Observe performance

Export metrics for your monitoring stack (Prometheus text format is supported):

```bash
meeting-memory metrics --db "$MEETING_MEMORY_DB" --format prometheus
```

Run benchmarks to validate capacity before scaling up:

```bash
meeting-memory benchmark --dataset medium
```

See [`docs/performance.md`](../performance.md) for the full benchmarking guide and
[`docs/benchmarks.md`](../benchmarks.md) for visualized results.

## Production checklist

- [ ] Database on durable storage with automated backups
- [ ] Health probe wired to `/health`
- [ ] Metrics scraped (`--format prometheus`)
- [ ] Automation pipeline scheduled with log retention
- [ ] Restore tested from a recent backup
- [ ] Resource limits set (see the production compose example)

See the [release checklist](../../RELEASE_CHECKLIST.md) before cutting a versioned
deployment.
