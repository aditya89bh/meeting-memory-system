"""FastAPI application factory for the Meeting Memory System REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from .dependencies import get_db_path
from .errors import register_error_handlers
from .routers import graph, health, intelligence, meetings, memories, search
from .version import API_DESCRIPTION, API_TITLE, API_VERSION


def create_app(*, db_path: str | Path | None = None) -> FastAPI:
    """Build a configured FastAPI application.

    When ``db_path`` is provided the database dependency is overridden to point
    at it, which is how the SDK (local-embedded mode) and the test-suite bind an
    app to a specific SQLite store without touching environment variables.
    """
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(meetings.router)
    app.include_router(memories.router)
    app.include_router(search.router)
    app.include_router(graph.router)
    app.include_router(intelligence.router)

    if db_path is not None:
        resolved = Path(db_path)
        app.dependency_overrides[get_db_path] = lambda: resolved
    return app


app = create_app()
"""Module-level app for ``uvicorn meeting_memory.api.app:app``."""
