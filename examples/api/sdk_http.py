#!/usr/bin/env python3
"""Python SDK workflow in HTTP mode against a running API server.

First start a server in another terminal::

    python examples/api/serve.py --db atlas.db --port 8000

Then run::

    python examples/api/sdk_http.py --base-url http://127.0.0.1:8000

The HTTP client exposes the exact same method surface as local mode.
"""

from __future__ import annotations

import argparse

from meeting_memory.sdk import MeetingMemoryClient


def main() -> None:
    """Connect to a remote API and run a small read-only workflow."""
    parser = argparse.ArgumentParser(description="Exercise the SDK over HTTP.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL.")
    args = parser.parse_args()

    with MeetingMemoryClient.connect(args.base_url) as client:
        print(f"mode: {client.mode}")
        print(f"health: {client.health()}")
        print(f"meetings: {client.meetings()['pagination']['total']}")
        print(f"search 'postgres': {client.search('postgres')['stats']['returned']} result(s)")
        print(f"insights: {client.insights()['pagination']['total']}")
        print(f"graph nodes: {client.graph()['nodes']}")


if __name__ == "__main__":
    main()
