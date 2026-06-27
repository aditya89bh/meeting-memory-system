# Tutorial 7 — REST API

The system ships a FastAPI application that exposes every capability over HTTP, plus an
interactive dashboard and OpenAPI docs.

## Install and prepare data

```bash
pip install -e ".[api]"
meeting-memory import-dir examples/organizations/startup --db atlas.db --recursive
```

## Start the server

```bash
# Convenience launcher
python examples/api/serve.py --db atlas.db --port 8000

# Or uvicorn directly (database from an environment variable)
MEETING_MEMORY_DB=atlas.db uvicorn meeting_memory.api.app:app --port 8000
```

Now open:

- Dashboard: `http://127.0.0.1:8000/dashboard`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health: `http://127.0.0.1:8000/health`

## Call the API

```bash
# Health and version
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/version

# Stats
curl http://127.0.0.1:8000/meetings/stats

# Search (ranked retrieval)
curl "http://127.0.0.1:8000/search?q=risk&limit=5"

# Graph summary
curl "http://127.0.0.1:8000/graph"

# Intelligence report (markdown)
curl "http://127.0.0.1:8000/intelligence/report?format=markdown"
```

## Key endpoint groups

| Group | Endpoints |
|---|---|
| Meetings | `GET /meetings`, `GET /meetings/{id}`, `GET /meetings/stats`, `POST /meetings/import` |
| Memories | `GET /memories`, `GET /memories/{id}` |
| Search | `GET /search` |
| Graph | `GET /graph`, `GET /graph/neighbors`, `GET /graph/path` |
| Intelligence | `GET /intelligence/insights`, `/metrics`, `/recommendations`, `/report` |
| Automation | `POST /automation/run`, `GET /automation/jobs`, `GET /automation/logs` |

## The dashboard

The dashboard is server-rendered HTML (no JavaScript build step) with pages for the
overview, meetings, search, graph, insights, reports, and jobs. It is ideal for
demoing the system to non-technical stakeholders.

For programmatic access from Python, use the [Python SDK](python-sdk.md) instead of raw
HTTP.
