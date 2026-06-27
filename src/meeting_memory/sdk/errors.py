"""Error types raised by the Python SDK."""

from __future__ import annotations

from typing import Any


class APIError(RuntimeError):
    """Raised when the API (local or HTTP) returns a non-2xx response.

    The structured error payload returned by the API is preserved so callers can
    branch on ``status_code`` or the stable ``error`` identifier.
    """

    def __init__(
        self,
        status_code: int,
        *,
        error: str = "error",
        detail: str = "",
        correlation_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{status_code}] {error}: {detail}")
        self.status_code = status_code
        self.error = error
        self.detail = detail
        self.correlation_id = correlation_id
        self.payload = payload or {}

    @classmethod
    def from_payload(cls, status_code: int, payload: Any) -> APIError:
        """Build an :class:`APIError` from a decoded JSON error body."""
        if isinstance(payload, dict):
            return cls(
                status_code,
                error=str(payload.get("error", "error")),
                detail=str(payload.get("detail", "")),
                correlation_id=payload.get("correlation_id"),
                payload=payload,
            )
        return cls(status_code, detail=str(payload))
