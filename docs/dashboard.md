# Web dashboard

The dashboard is a lightweight, server-rendered web UI mounted on the API. It is
intentionally simple: no client build system, no JavaScript framework, and no
authentication. Every page reads its data through the same service layer as the
REST API and CLI.

## Running it

Start the API (the dashboard is included):

```bash
python examples/api/serve.py --db atlas.db --port 8000
```

Then open `http://127.0.0.1:8000/dashboard`. The site root (`/`) redirects there.

## Pages

| Path | Page | Shows |
| --- | --- | --- |
| `/dashboard` | Overview | Meeting/memory/graph counts, organizational health, and memory breakdowns by type and status. |
| `/dashboard/meetings` | Meetings | A table of stored meetings (id, title, date, participants). |
| `/dashboard/search` | Search | A search box; submitting `?q=` runs ranked retrieval and lists scored results. |
| `/dashboard/graph` | Graph | Node/edge counts, breakdowns by node type and relationship, and a node sample. |
| `/dashboard/insights` | Insights | Discovered insights and prioritised recommendations. |
| `/dashboard/reports` | Reports | The full organizational-intelligence report rendered as Markdown text. |
| `/dashboard/jobs` | Jobs | Recorded automation runs and recent structured log lines. |

## How it is built

- **`api/dashboard/render.py`** — small, dependency-free HTML helpers: a shared
  layout with a navigation bar and inline CSS, plus `cards`, `table`, and
  `section` builders. All dynamic text is HTML-escaped.
- **`api/dashboard/router.py`** — one route per page. Routes depend on the same
  injected services (`MeetingService`, `RetrievalService`, `GraphService`,
  `IntelligenceService`, `AutomationService`) and return `HTMLResponse`.

The dashboard router is excluded from the OpenAPI schema (`include_in_schema=
False`) so it does not clutter the API documentation.

## Capturing pages locally

To view the rendered pages without running a server, capture them to HTML files:

```bash
python examples/api/capture_dashboard.py --out examples/api/dashboard
```

This seeds a throwaway database with the bundled transcripts, renders every page
through the in-process app, and writes `overview.html`, `meetings.html`,
`search.html`, `graph.html`, `insights.html`, `reports.html`, and `jobs.html`.
Open any of them in a browser.

## Future authentication support

The dashboard inherits whatever authentication is added to the API. Because the
pages are plain server-rendered routes behind the same dependency-injection
system, an auth dependency added in `create_app` (or to the dashboard router
include) would protect them without changing the rendering code. A login page and
session cookie could be layered on using the existing correlation-id middleware
and `request.state` for the authenticated principal.
