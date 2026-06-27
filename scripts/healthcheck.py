#!/usr/bin/env python
"""Container health check: probe the API ``/health`` endpoint.

Exits 0 when the API reports healthy and non-zero otherwise, which is what
Docker's ``HEALTHCHECK`` and Compose health checks expect. Uses only the
standard library so it adds no runtime dependencies.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    """Return 0 if the API health endpoint reports a healthy status."""
    host = os.environ.get("MEETING_MEMORY_HOST", "127.0.0.1")
    if host == "0.0.0.0":
        host = "127.0.0.1"
    port = os.environ.get("MEETING_MEMORY_PORT", "8000")
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                print(f"health check failed: HTTP {response.status}", file=sys.stderr)
                return 1
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"health check error: {exc}", file=sys.stderr)
        return 1

    status = payload.get("status")
    if status not in {"ok", "healthy"}:
        print(f"health check unhealthy: {status}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
