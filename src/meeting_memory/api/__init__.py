"""REST API package (Phase 8): FastAPI application over the service layer."""

from __future__ import annotations

from .app import create_app
from .version import API_DESCRIPTION, API_TITLE, API_VERSION

__all__ = ["API_DESCRIPTION", "API_TITLE", "API_VERSION", "create_app"]
