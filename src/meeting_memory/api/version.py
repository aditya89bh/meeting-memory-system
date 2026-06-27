"""Version and metadata constants for the REST API and OpenAPI document."""

from __future__ import annotations

from .. import __version__

API_VERSION: str = __version__
"""Reported in the ``X-API-Version`` header, ``GET /version``, and OpenAPI."""

API_TITLE: str = "Meeting Memory System API"

API_DESCRIPTION: str = (
    "Deterministic REST API over the Meeting Memory System. Import transcripts, "
    "search organizational memory, traverse the knowledge graph, compute decision "
    "intelligence, and run automation pipelines. The API, Python SDK, CLI, and "
    "dashboard all share one service layer and the same SQLite store."
)
