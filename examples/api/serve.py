#!/usr/bin/env python3
"""Start the REST API server against a chosen database.

Run from the repository root::

    python examples/api/serve.py --db atlas.db --port 8000

Then browse the dashboard at http://127.0.0.1:8000/dashboard, the Swagger UI at
/docs, and ReDoc at /redoc, or point the SDK at it in HTTP mode::

    from meeting_memory.sdk import MeetingMemoryClient
    client = MeetingMemoryClient.connect("http://127.0.0.1:8000")
"""

from __future__ import annotations

import argparse

import uvicorn

from meeting_memory.api.app import create_app


def main() -> None:
    """Parse arguments and run the API with uvicorn."""
    parser = argparse.ArgumentParser(description="Serve the Meeting Memory System API.")
    parser.add_argument("--db", default="meeting-memory.db", help="SQLite database path.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    args = parser.parse_args()

    app = create_app(db_path=args.db)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
