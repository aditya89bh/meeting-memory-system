#!/usr/bin/env python3
"""Capture the rendered dashboard pages to HTML files (local "screenshots").

Run from the repository root::

    python examples/api/capture_dashboard.py --out examples/api/dashboard

This seeds a throwaway database with the bundled transcripts, renders every
dashboard page through the in-process API, and writes the HTML to disk. Open the
files in a browser to view the dashboard without running a server.
"""

from __future__ import annotations

import argparse
import tempfile
import warnings
from pathlib import Path

from meeting_memory.services import MeetingService

HISTORY = Path(__file__).resolve().parents[2] / "examples" / "history"

PAGES = {
    "overview.html": "/dashboard",
    "meetings.html": "/dashboard/meetings",
    "search.html": "/dashboard/search?q=postgres",
    "graph.html": "/dashboard/graph",
    "insights.html": "/dashboard/insights",
    "reports.html": "/dashboard/reports",
    "jobs.html": "/dashboard/jobs",
}


def main() -> None:
    """Render and save every dashboard page as an HTML file."""
    parser = argparse.ArgumentParser(description="Capture dashboard pages to HTML.")
    parser.add_argument("--out", default="examples/api/dashboard", help="Output directory.")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mm-dash-") as tmp:
        db = Path(tmp) / "atlas.db"
        MeetingService(db).import_path(HISTORY, recursive=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient

        from meeting_memory.api.app import create_app

        client = TestClient(create_app(db_path=db))
        for filename, path in PAGES.items():
            response = client.get(path)
            response.raise_for_status()
            (out / filename).write_text(response.text, encoding="utf-8")
            print(f"wrote {out / filename}")


if __name__ == "__main__":
    main()
