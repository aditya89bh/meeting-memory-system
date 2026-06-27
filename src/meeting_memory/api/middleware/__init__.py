"""HTTP middleware: correlation ids, request timing/logging, and headers.

A single middleware attaches a correlation id to every request (honouring an
inbound ``X-Correlation-ID`` header or minting a new one), times the request,
emits a structured log line, and stamps correlation/version/timing headers onto
the response. The correlation id is stored on ``request.state`` so the structured
error handlers include it in their payloads.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..errors import CORRELATION_HEADER
from ..version import API_VERSION

VERSION_HEADER = "X-API-Version"
PROCESS_TIME_HEADER = "X-Process-Time-Ms"

logger = logging.getLogger("meeting_memory.api")

CallNext = Callable[[Request], Awaitable[Response]]


def _new_correlation_id() -> str:
    """Return a fresh correlation id (reuses the connector log id generator)."""
    from ...connectors.logging import new_correlation_id

    return new_correlation_id()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Correlation id, timing, structured logging, and response headers."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        """Process one request: correlate, time, log, and stamp headers."""
        correlation_id = request.headers.get(CORRELATION_HEADER) or _new_correlation_id()
        request.state.correlation_id = correlation_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers[CORRELATION_HEADER] = correlation_id
        response.headers[VERSION_HEADER] = API_VERSION
        response.headers[PROCESS_TIME_HEADER] = f"{duration_ms:.3f}"
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 3),
                    "correlation_id": correlation_id,
                }
            )
        )
        return response


def register_middleware(app: FastAPI) -> None:
    """Attach the observability middleware to the application."""
    app.add_middleware(ObservabilityMiddleware)
