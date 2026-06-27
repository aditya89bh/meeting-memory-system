# API, SDK & Dashboard examples

These examples exercise the Phase 8 platform surface: the FastAPI REST API, the
Python SDK (local and HTTP modes), the web dashboard, and OpenAPI. Everything is
deterministic, offline, and backed by SQLite.

Run all commands from the repository root.

## Python SDK (local mode, end-to-end)

```bash
python examples/api/sdk_quickstart.py
```

Imports the bundled transcripts into a throwaway database, then runs search, the
knowledge graph, intelligence, reporting, and an automation pipeline through the
in-process client. Local mode runs the real API routers and service layer with
no network and no server.

## Serve the API

```bash
python examples/api/serve.py --db atlas.db --port 8000
```

- Dashboard: <http://127.0.0.1:8000/dashboard>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

## Python SDK (HTTP mode)

With a server running:

```bash
python examples/api/sdk_http.py --base-url http://127.0.0.1:8000
```

The HTTP client exposes the same methods as local mode.

## REST API with curl

With a server running:

```bash
bash examples/api/curl.sh
```

## Dashboard screenshots (rendered locally)

```bash
python examples/api/capture_dashboard.py --out examples/api/dashboard
```

Writes `overview.html`, `meetings.html`, `search.html`, `graph.html`,
`insights.html`, `reports.html`, and `jobs.html` so you can open the dashboard
pages in a browser without running a server.
