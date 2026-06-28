# Deployment

The Meeting Memory System ships with everything needed to run the REST API in a
container: a multi-stage `Dockerfile`, a `docker-compose.yml`, a health-check
probe, environment-driven configuration, and a production startup script. All
state lives in a single SQLite database on a mounted volume.

## Image

The `Dockerfile` builds in two stages:

1. **build** — installs `build` and produces a wheel from the source tree.
2. **runtime** — a slim Python image that installs the wheel with the `api` and
   `sdk` extras, adds the startup and health-check scripts, creates an
   unprivileged `appuser`, declares a `/data` volume, exposes port 8000, and sets
   a container `HEALTHCHECK`.

```bash
docker build -t meeting-memory:latest .
docker run -d -p 8000:8000 -v meeting-memory-data:/data meeting-memory:latest
curl localhost:8000/health
```

## Compose

```bash
docker compose up -d        # build + start with a named volume and health check
docker compose config       # validate the compose file
docker compose logs -f
```

A production-oriented example that pins an image tag and adds resource limits
lives at [`examples/ops/deployment/docker-compose.prod.yml`](https://github.com/aditya89bh/meeting-memory-system/blob/main/examples/ops/deployment/docker-compose.prod.yml):

```bash
docker compose -f examples/ops/deployment/docker-compose.prod.yml up -d
```

## Configuration

All configuration is read from the environment, so the same image runs unchanged
everywhere:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MEETING_MEMORY_DB` | `/data/meeting-memory.db` | SQLite database path. |
| `MEETING_MEMORY_HOST` | `0.0.0.0` | Bind host. |
| `MEETING_MEMORY_PORT` | `8000` | Bind port. |
| `MEETING_MEMORY_WORKERS` | `1` | uvicorn worker count (keep at 1 for SQLite). |
| `MEETING_MEMORY_LOG_LEVEL` | `info` | uvicorn log level. |

> **SQLite & workers.** SQLite is single-writer. Keep `MEETING_MEMORY_WORKERS=1`
> for write-heavy workloads; read-heavy deployments can scale workers but should
> expect SQLite's normal concurrency semantics.

## Startup & health

`scripts/start.sh` ensures the database directory exists and launches uvicorn
with the configured host/port/workers. The container `HEALTHCHECK` runs
`scripts/healthcheck.py`, which probes `GET /health` over the loopback interface
and exits non-zero unless the API reports `status: ok`.

```bash
# Run the same startup path locally (without Docker)
MEETING_MEMORY_DB=atlas.db ./scripts/start.sh
```

## Persistence & backups

The database lives on the `/data` volume. Back it up without stopping the
container using the CLI (see [`docs/backup.md`](backup.md)):

```bash
meeting-memory backup --db /data/meeting-memory.db -o /data/backup.db
```

## Observability

The API emits `X-Correlation-ID`, `X-API-Version`, and `X-Process-Time-Ms`
response headers and structured request logs. Application metrics are available
in Prometheus text format:

```bash
meeting-memory metrics --db /data/meeting-memory.db --format prometheus
```
