"""Structured error responses and exception handlers for the REST API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from ...exceptions import (
    DuplicateMeetingError,
    MeetingMemoryError,
    MeetingNotFoundError,
    MemoryNotFoundError,
    NodeNotFoundError,
)

CORRELATION_HEADER = "X-Correlation-ID"


class ErrorResponse(BaseModel):
    """A machine-readable error payload returned for every failed request."""

    error: str = Field(description="A stable error type identifier.")
    detail: str = Field(description="A human-readable description of the failure.")
    status_code: int = Field(description="The HTTP status code.")
    correlation_id: str | None = Field(
        default=None, description="Correlation id linking the response to its logs."
    )


class ValidationErrorItem(BaseModel):
    """A single request-validation problem."""

    location: list[str | int] = Field(description="Path to the offending field.")
    message: str = Field(description="Why the field failed validation.")
    type: str = Field(description="The validation rule that failed.")


class ValidationErrorResponse(BaseModel):
    """The payload returned for request-validation (422) failures."""

    error: str = Field(default="validation_error")
    detail: str = Field(default="Request validation failed.")
    status_code: int = Field(default=422)
    errors: list[ValidationErrorItem] = Field(default_factory=list)
    correlation_id: str | None = Field(default=None)


def _correlation_id(request: Request) -> str | None:
    value = getattr(request.state, "correlation_id", None)
    return value if isinstance(value, str) else None


def status_for(exc: MeetingMemoryError) -> int:
    """Map a domain exception to an HTTP status code."""
    if isinstance(exc, MemoryNotFoundError | MeetingNotFoundError | NodeNotFoundError):
        return 404
    if isinstance(exc, DuplicateMeetingError):
        return 409
    return 400


def _headers(correlation_id: str | None) -> dict[str, str]:
    return {CORRELATION_HEADER: correlation_id} if correlation_id else {}


async def meeting_memory_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render any :class:`MeetingMemoryError` as a structured error response."""
    assert isinstance(exc, MeetingMemoryError)
    correlation_id = _correlation_id(request)
    status_code = status_for(exc)
    body = ErrorResponse(
        error=type(exc).__name__,
        detail=str(exc),
        status_code=status_code,
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=status_code, content=body.model_dump(), headers=_headers(correlation_id)
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render FastAPI request-validation failures as a structured 422."""
    assert isinstance(exc, RequestValidationError)
    correlation_id = _correlation_id(request)
    items = [
        ValidationErrorItem(
            location=[part for part in error.get("loc", ()) if isinstance(part, str | int)],
            message=str(error.get("msg", "")),
            type=str(error.get("type", "")),
        )
        for error in exc.errors()
    ]
    body = ValidationErrorResponse(errors=items, correlation_id=correlation_id)
    return JSONResponse(
        status_code=422, content=body.model_dump(), headers=_headers(correlation_id)
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render Starlette HTTP errors (e.g. 404 routes) in the structured shape."""
    assert isinstance(exc, StarletteHTTPException)
    correlation_id = _correlation_id(request)
    body = ErrorResponse(
        error="http_error",
        detail=str(exc.detail),
        status_code=exc.status_code,
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=exc.status_code, content=body.model_dump(), headers=_headers(correlation_id)
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach all structured exception handlers to the application."""
    app.add_exception_handler(MeetingMemoryError, meeting_memory_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
