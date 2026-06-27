"""Server-side HTML rendering helpers for the dashboard.

Pages are rendered with small, dependency-free Python helpers (no template
engine, no client build step). All dynamic text is HTML-escaped.
"""

from __future__ import annotations

from collections.abc import Iterable
from html import escape

NAV = (
    ("Overview", "/dashboard"),
    ("Meetings", "/dashboard/meetings"),
    ("Search", "/dashboard/search"),
    ("Graph", "/dashboard/graph"),
    ("Insights", "/dashboard/insights"),
    ("Reports", "/dashboard/reports"),
    ("Jobs", "/dashboard/jobs"),
)

_STYLE = """
:root { --bg:#0f172a; --panel:#1e293b; --muted:#94a3b8; --text:#e2e8f0;
  --accent:#38bdf8; --border:#334155; --chip:#0ea5e9; }
* { box-sizing: border-box; }
body { margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  background:var(--bg); color:var(--text); }
header { background:var(--panel); border-bottom:1px solid var(--border); padding:0 24px; }
.brand { font-weight:700; font-size:18px; padding:16px 0; display:inline-block; }
nav { display:inline-flex; gap:4px; margin-left:24px; flex-wrap:wrap; }
nav a { color:var(--muted); text-decoration:none; padding:8px 12px; border-radius:8px;
  font-size:14px; }
nav a:hover { color:var(--text); background:#0b1220; }
nav a.active { color:#04293a; background:var(--accent); font-weight:600; }
main { max-width:1100px; margin:0 auto; padding:24px; }
h1 { font-size:22px; margin:0 0 16px; }
h2 { font-size:16px; margin:24px 0 8px; color:var(--muted); text-transform:uppercase;
  letter-spacing:.05em; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }
.card { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:16px; }
.card .n { font-size:28px; font-weight:700; }
.card .l { color:var(--muted); font-size:13px; margin-top:4px; }
table { width:100%; border-collapse:collapse; background:var(--panel);
  border:1px solid var(--border); border-radius:12px; overflow:hidden; }
th, td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--border);
  font-size:14px; vertical-align:top; }
th { color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; }
tr:last-child td { border-bottom:none; }
.chip { display:inline-block; background:#0b1220; border:1px solid var(--border);
  color:var(--accent); border-radius:999px; padding:2px 10px; font-size:12px; }
form.search { display:flex; gap:8px; margin-bottom:8px; }
input[type=text] { flex:1; background:#0b1220; border:1px solid var(--border); color:var(--text);
  padding:10px 12px; border-radius:8px; font-size:14px; }
button { background:var(--accent); color:#04293a; border:none; padding:10px 16px;
  border-radius:8px; font-weight:600; cursor:pointer; }
pre { background:#0b1220; border:1px solid var(--border); border-radius:12px; padding:16px;
  overflow:auto; font-size:13px; line-height:1.5; }
.muted { color:var(--muted); }
a { color:var(--accent); }
"""


def layout(title: str, active: str, body: str) -> str:
    """Wrap page ``body`` in the shared dashboard layout."""
    links = "".join(
        f'<a class="{"active" if label == active else ""}" href="{href}">{escape(label)}</a>'
        for label, href in NAV
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} · Meeting Memory</title><style>{_STYLE}</style></head><body>"
        f'<header><span class="brand">Meeting Memory</span><nav>{links}</nav></header>'
        f"<main>{body}</main></body></html>"
    )


def cards(items: Iterable[tuple[str, object]]) -> str:
    """Render a row of metric cards from ``(label, value)`` pairs."""
    parts = [
        f'<div class="card"><div class="n">{escape(str(value))}</div>'
        f'<div class="l">{escape(label)}</div></div>'
        for label, value in items
    ]
    return f'<div class="cards">{"".join(parts)}</div>'


def table(headers: list[str], rows: Iterable[Iterable[object]]) -> str:
    """Render a table; all cell values are escaped."""
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(cell))}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    if not body_rows:
        span = len(headers)
        body_rows.append(f'<tr><td colspan="{span}" class="muted">No data.</td></tr>')
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def section(title: str) -> str:
    """Render a section heading."""
    return f"<h2>{escape(title)}</h2>"
