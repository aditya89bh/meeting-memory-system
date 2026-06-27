"""Python SDK for the Meeting Memory System (Phase 8).

The SDK exposes a single :class:`MeetingMemoryClient` with one method per major
capability. It supports two interchangeable transports with an identical surface:
a local in-process mode bound to a SQLite database, and an HTTP mode talking to a
remote API server. Both run through the same FastAPI routers and service layer.

Example (local mode)::

    from meeting_memory.sdk import MeetingMemoryClient

    with MeetingMemoryClient.local("atlas.db") as client:
        client.import_directory("examples/history")
        hits = client.search("postgres")
        report = client.report(fmt="markdown")
"""

from __future__ import annotations

from .client import MeetingMemoryClient
from .errors import APIError

__all__ = ["APIError", "MeetingMemoryClient"]
