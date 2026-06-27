# REST API

The Meeting Memory System exposes a deterministic FastAPI application over the
shared service layer. The API, CLI, Python SDK, and dashboard all call the same
services and the same SQLite store — there is no duplicated logic and no network
or LLM dependency.

## Architecture

```
HTTP request
  └─▶ ObservabilityMiddleware  (correlation id, timing, structured log, headers)
        └─▶ router  (api/routers/*.py)
              └─▶ dependency-injected service  (services/*.py)
                    └─▶ parser / extraction / storage / retrieval / graph /
                        intelligence / connectors  (SQLite)
```

- **`api/app.py`** — the application factory `create_app(db_path=...)` and the
  module-level `app` for `uvicorn meeting_memory.api.app:app`.
- **`api/version.py`** — title, version (mirrors the package version), and the
  OpenAPI description.
- **`api/dependencies/`** — the database-path resolver (the `MEETING_MEMORY_DB`
  env var, overridable per app/test), one provider per service, and validated
  pagination.
- **`api/routers/`** — `health`, `meetings`, `memories`, `search`, `graph`,
  `intelligence`, and `automation`, plus the dashboard router.
- **`api/schemas/`** — typed Pydantic request/response models built from the
  existing domain `to_dict()` shapes via `model_validate`.
- **`api/errors/`** — `ErrorResponse`, `ValidationErrorResponse`, and the
  exception handlers that map domain errors to HTTP status codes.
- **`api/middleware/`** — correlation ids, request timing, structured request
  logging, and response headers.

## Running the API

```bash
# Helper script (binds the app to a database)
python examples/api/serve.py --db atlas.db --port 8000

# Or with uvicorn directly (database from the MEETING_MEMORY_DB env var)
MEETING_MEMORY_DB=atlas.db uvicorn meeting_memory.api.app:app --port 8000
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI document: `http://127.0.0.1:8000/openapi.json`
- Dashboard: `http://127.0.0.1:8000/dashboard`

## Endpoint reference

| Method & path | Description |
| --- | --- |
| `GET /health` | Liveness probe (`{"status": "ok", "version": ...}`). |
| `GET /version` | API name and version. |
| `POST /meetings/import` | Import by server-side `path` or inline `content` (with `format`); supports `recursive`, `deduplicate`, `dry_run`. Returns `201`. |
| `GET /meetings` | Paginated meeting list (`limit`, `offset`). |
| `GET /meetings/stats` | Store-wide counts by memory type and status. |
| `GET /meetings/{id}` | A single meeting (`404` if absent). |
| `GET /memories` | Paginated memory list filtered by `type`, `speaker`, `meeting`, `status`, `min_confidence`. |
| `GET /memories/{id}` | A single memory (`404` if absent). |
| `GET /search` | Ranked retrieval (`q`, `type`, `speaker`, `status`, `meeting`, `min_confidence`, `date_from/to`, `order`, `context_size`, `limit`, `offset`). |
| `GET /graph` | Graph counts plus an optional node listing (`type`, `limit`). |
| `GET /graph/neighbors` | Neighbourhood traversal (`node_id`, `depth`, `type`, `relationship`, `limit`). |
| `GET /graph/path` | Shortest path between `source` and `target` (`depth`, `relationship`). |
| `GET /insights` | Paginated insights (`type`, `project`, `person`, `meeting`). |
| `GET /metrics` | Organizational-health snapshot. |
| `GET /recommendations` | Paginated, prioritised recommendations. |
| `GET /reports` | Rendered report (`format` = `json`/`markdown`/`text`). |
| `POST /automation/run` | Run a pipeline by `config` path or inline `pipeline` (with `dry_run`). |
| `GET /automation/jobs` | Recorded automation runs (paginated). |
| `GET /automation/logs` | Structured logs (`correlation_id`, paginated). |

## Pagination

List endpoints return a `pagination` envelope alongside `items`:

```json
{
  "pagination": {"limit": 25, "offset": 0, "count": 25, "total": 142},
  "items": [ ... ]
}
```

`limit` is validated to `1..500`; `offset` must be `>= 0`.

## Errors

Every failure returns a structured body. Domain errors map to status codes:

| Exception | Status |
| --- | --- |
| `MemoryNotFoundError`, `MeetingNotFoundError`, `NodeNotFoundError` | `404` |
| `DuplicateMeetingError` | `409` |
| other `MeetingMemoryError` | `400` |
| request validation | `422` |

```json
{
  "error": "MeetingNotFoundError",
  "detail": "no meeting with id 'nope'",
  "status_code": 404,
  "correlation_id": "4a0088ffffae"
}
```

Validation failures (`422`) additionally include an `errors` array describing
each offending field.

## Observability

The middleware mints a correlation id for every request (or honours an inbound
`X-Correlation-ID`), times the request, emits a structured JSON log line on the
`meeting_memory.api` logger, and stamps these response headers:

- `X-Correlation-ID` — also echoed in error payloads.
- `X-API-Version` — the API version.
- `X-Process-Time-Ms` — server-side processing time in milliseconds.

## OpenAPI

The OpenAPI document is generated automatically from the typed routes and
schemas, enriched with tag descriptions, contact/license metadata, and
request-body examples for import and automation. It is served at `/openapi.json`
and rendered by Swagger UI (`/docs`) and ReDoc (`/redoc`).

## Deployment

The app is a standard ASGI application. Bind it to a database with the
`MEETING_MEMORY_DB` environment variable (or `create_app(db_path=...)`), then run
it under any ASGI server:

```bash
MEETING_MEMORY_DB=/data/atlas.db uvicorn meeting_memory.api.app:app \
  --host 0.0.0.0 --port 8000 --workers 4
```

Because each request opens a short-lived SQLite connection, the app is safe to
run with multiple workers against a single database file for read-heavy traffic.

## Future authentication support

The API ships without authentication by design (it is a platform foundation).
Authentication and authorization can be layered in without touching the routers
or services: add an auth dependency to the router includes (or a global
dependency in `create_app`), and add a middleware to validate credentials and
attach a principal to `request.state`. The correlation-id middleware and
structured errors already provide the request context such a layer would build
on.
