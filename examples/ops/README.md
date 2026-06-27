# Production operations examples (Phase 9)

These self-contained scripts demonstrate the Phase 9 capabilities: benchmark
datasets, the replay engine, performance benchmarks, backup/restore, and Docker
deployment. They use only deterministic, seeded data and temporary directories,
so they leave no artifacts behind.

## Scripts

| Script | What it shows |
| --- | --- |
| `generate_dataset.py` | Generate a deterministic dataset (e.g. a large organization) to disk. |
| `run_benchmarks.py` | Run the performance benchmarks and print or save a report. |
| `replay_demo.py` | Replay meetings: all, by project, by person, and step-by-step. |
| `backup_restore.py` | Physical backup/restore and logical snapshot/import round trips. |
| `deployment/docker-compose.prod.yml` | A production-oriented Compose example. |

## Running

```bash
# Generate a large organization dataset (thousands of memories).
python examples/ops/generate_dataset.py --dataset enterprise --out /tmp/org

# Benchmark the medium dataset over three iterations.
python examples/ops/run_benchmarks.py --dataset medium --iterations 3

# Replay and recovery demos.
python examples/ops/replay_demo.py
python examples/ops/backup_restore.py
```

## CLI equivalents

Every script mirrors a CLI command:

```bash
meeting-memory benchmark --dataset medium --iterations 3
meeting-memory replay --db meeting-memory.db --timeline
meeting-memory backup --db meeting-memory.db -o backup.db
meeting-memory restore --db restored.db backup.db
meeting-memory metrics --db meeting-memory.db --format prometheus
meeting-memory profile --db meeting-memory.db --operation intelligence
```

## Docker

Build and run the API with the repository's Dockerfile and Compose file:

```bash
docker build -t meeting-memory:latest .
docker compose up -d
curl localhost:8000/health
```

The production Compose example pins an image tag and adds resource limits:

```bash
docker compose -f examples/ops/deployment/docker-compose.prod.yml up -d
```
