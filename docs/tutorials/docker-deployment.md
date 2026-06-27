# Tutorial 9 — Docker deployment

The repository ships a multi-stage `Dockerfile` and a `docker-compose.yml` so you can
run the API and dashboard in a container with persistent storage.

## Build the image

```bash
docker build -t meeting-memory:latest .
```

The build uses a multi-stage layout: a builder stage produces a wheel, and a slim
runtime stage installs it with the `api` and `sdk` extras and runs as an unprivileged
user.

## Run with Docker

```bash
docker run --rm -p 8000:8000 \
  -e MEETING_MEMORY_DB=/data/atlas.db \
  -v meeting-memory-data:/data \
  meeting-memory:latest
```

Then open `http://127.0.0.1:8000/dashboard`.

## Run with Docker Compose

```bash
docker compose up --build
```

`docker-compose.yml` maps port 8000, sets the database path, and mounts a named volume
at `/data` so your data survives container restarts.

## Configuration

The container is configured entirely through environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MEETING_MEMORY_DB` | `/data/meeting-memory.db` | SQLite database path |
| `MEETING_MEMORY_HOST` | `0.0.0.0` | Bind host |
| `MEETING_MEMORY_PORT` | `8000` | Bind port |
| `MEETING_MEMORY_WORKERS` | `1` | uvicorn worker count |
| `MEETING_MEMORY_LOG_LEVEL` | `info` | Log level |

## Health checks

The image includes `scripts/healthcheck.py`, which probes `/health`. Compose and most
orchestrators use it to gate readiness. You can run it manually inside the container:

```bash
docker compose exec meeting-memory python scripts/healthcheck.py
```

## Importing data into the container

Mount a directory of transcripts and import them with a one-off command:

```bash
docker run --rm \
  -e MEETING_MEMORY_DB=/data/atlas.db \
  -v meeting-memory-data:/data \
  -v "$PWD/examples/organizations:/transcripts:ro" \
  meeting-memory:latest \
  meeting-memory import-dir /transcripts --db /data/atlas.db --recursive
```

A production-oriented compose file with image pinning and resource limits is provided in
[`examples/ops/deployment/docker-compose.prod.yml`](../../examples/ops/deployment/docker-compose.prod.yml).

Next: [Production deployment](production-deployment.md).
