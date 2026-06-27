"""System endpoints: liveness and version reporting."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..version import API_TITLE, API_VERSION

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: str = Field(examples=["ok"])
    version: str = Field(examples=[API_VERSION])


class VersionResponse(BaseModel):
    """Version and identity payload."""

    name: str = Field(examples=[API_TITLE])
    version: str = Field(examples=[API_VERSION])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
def health() -> HealthResponse:
    """Return ``ok`` when the service is running."""
    return HealthResponse(status="ok", version=API_VERSION)


@router.get("/version", response_model=VersionResponse, summary="Service version")
def version() -> VersionResponse:
    """Return the API name and version."""
    return VersionResponse(name=API_TITLE, version=API_VERSION)
