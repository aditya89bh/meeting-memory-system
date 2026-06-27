"""The Meeting Memory System Python SDK client.

``MeetingMemoryClient`` exposes one method per major capability and supports two
interchangeable transports with an identical surface:

* **local mode** — an in-process ASGI transport bound to a SQLite database, so
  calls run through the exact same FastAPI routers and service layer as the HTTP
  API, with no network and no running server.
* **HTTP mode** — a real HTTP client talking to a remote API server.

Both modes go through the same request path, so behaviour is identical and there
is no duplicated logic.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import httpx

from .errors import APIError

LOCAL_BASE_URL = "http://meeting-memory.local"


def _clean(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop ``None`` values and empty lists so they are not sent as query args."""
    if params is None:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)) and not value:
            continue
        cleaned[key] = value
    return cleaned


_SUFFIX_FORMAT = {
    ".txt": "text",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
    ".csv": "csv",
}


class MeetingMemoryClient:
    """A unified client over the Meeting Memory System API (local or HTTP)."""

    def __init__(
        self,
        *,
        db: str | Path | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        if (db is None) == (base_url is None):
            raise ValueError("provide exactly one of 'db' (local mode) or 'base_url' (HTTP mode)")
        self._client: httpx.Client
        if db is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from starlette.testclient import TestClient

            from ..api.app import create_app

            self._client = TestClient(create_app(db_path=db), base_url=LOCAL_BASE_URL)
            self.mode = "local"
        else:
            self._client = httpx.Client(base_url=str(base_url), timeout=timeout)
            self.mode = "http"

    # --- construction helpers --------------------------------------------

    @classmethod
    def local(cls, db: str | Path) -> MeetingMemoryClient:
        """Create a client bound to a local SQLite database (in-process)."""
        return cls(db=db)

    @classmethod
    def connect(cls, base_url: str, *, timeout: float = 30.0) -> MeetingMemoryClient:
        """Create a client talking to a remote API server over HTTP."""
        return cls(base_url=base_url, timeout=timeout)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        """Close the underlying transport."""
        self._client.close()

    def __enter__(self) -> MeetingMemoryClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --- low-level request -----------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> dict[str, Any]:
        """Issue a request and return the decoded JSON body (raising on errors)."""
        response = self._client.request(method, path, params=_clean(params), json=json)
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.status_code >= 400:
            raise APIError.from_payload(response.status_code, data)
        return cast("dict[str, Any]", data)

    # --- system ----------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return the liveness payload."""
        return self.request("GET", "/health")

    def version(self) -> dict[str, Any]:
        """Return the API name and version."""
        return self.request("GET", "/version")

    # --- meetings & memories ---------------------------------------------

    def import_file(
        self,
        path: str | Path,
        *,
        fmt: str | None = None,
        deduplicate: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Import a single transcript file by uploading its content."""
        file_path = Path(path)
        resolved_fmt = fmt or _SUFFIX_FORMAT.get(file_path.suffix.lower(), "text")
        body = {
            "content": file_path.read_text(encoding="utf-8"),
            "format": resolved_fmt,
            "deduplicate": deduplicate,
            "dry_run": dry_run,
        }
        return self.request("POST", "/meetings/import", json=body)

    def import_directory(
        self,
        path: str | Path,
        *,
        recursive: bool = True,
        deduplicate: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Import a directory or archive by server-side path."""
        body = {
            "path": str(path),
            "recursive": recursive,
            "deduplicate": deduplicate,
            "dry_run": dry_run,
        }
        return self.request("POST", "/meetings/import", json=body)

    def meetings(self, *, limit: int | None = None, offset: int = 0) -> dict[str, Any]:
        """Return a page of stored meetings."""
        return self.request("GET", "/meetings", params={"limit": limit, "offset": offset})

    def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Return a single meeting by id."""
        return self.request("GET", f"/meetings/{meeting_id}")

    def stats(self) -> dict[str, Any]:
        """Return store-wide counts by memory type and lifecycle status."""
        return self.request("GET", "/meetings/stats")

    def memories(
        self,
        *,
        memory_type: list[str] | None = None,
        speaker: list[str] | None = None,
        meeting: list[str] | None = None,
        status: list[str] | None = None,
        min_confidence: float | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return a page of memories filtered by the common dimensions."""
        params = {
            "type": memory_type,
            "speaker": speaker,
            "meeting": meeting,
            "status": status,
            "min_confidence": min_confidence,
            "limit": limit,
            "offset": offset,
        }
        return self.request("GET", "/memories", params=params)

    def get_memory(self, memory_id: str) -> dict[str, Any]:
        """Return a single memory by id."""
        return self.request("GET", f"/memories/{memory_id}")

    # --- search ----------------------------------------------------------

    def search(
        self,
        q: str | None = None,
        *,
        memory_type: list[str] | None = None,
        speaker: list[str] | None = None,
        status: list[str] | None = None,
        meeting: list[str] | None = None,
        min_confidence: float | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        order: str = "relevance",
        context_size: int = 1,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Run a deterministic ranked retrieval query."""
        params = {
            "q": q,
            "type": memory_type,
            "speaker": speaker,
            "status": status,
            "meeting": meeting,
            "min_confidence": min_confidence,
            "date_from": date_from,
            "date_to": date_to,
            "order": order,
            "context_size": context_size,
            "limit": limit,
            "offset": offset,
        }
        return self.request("GET", "/search", params=params)

    # --- graph -----------------------------------------------------------

    def graph(
        self, *, node_type: list[str] | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """Return graph counts plus an optionally filtered node listing."""
        return self.request("GET", "/graph", params={"type": node_type, "limit": limit})

    def neighbors(
        self,
        node_id: str,
        *,
        depth: int = 1,
        node_type: list[str] | None = None,
        relationship: list[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Traverse the graph from a node and return its neighbourhood."""
        params = {
            "node_id": node_id,
            "depth": depth,
            "type": node_type,
            "relationship": relationship,
            "limit": limit,
        }
        return self.request("GET", "/graph/neighbors", params=params)

    def path(
        self,
        source: str,
        target: str,
        *,
        depth: int = 6,
        relationship: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a deterministic shortest path between two nodes, if any."""
        params = {
            "source": source,
            "target": target,
            "depth": depth,
            "relationship": relationship,
        }
        return self.request("GET", "/graph/path", params=params)

    # --- intelligence ----------------------------------------------------

    def insights(
        self,
        *,
        insight_type: list[str] | None = None,
        project: str | None = None,
        person: str | None = None,
        meeting: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return discovered organizational insights."""
        params = {
            "type": insight_type,
            "project": project,
            "person": person,
            "meeting": meeting,
            "limit": limit,
            "offset": offset,
        }
        return self.request("GET", "/insights", params=params)

    def metrics(
        self,
        *,
        project: str | None = None,
        person: str | None = None,
        meeting: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return the organizational-health metrics snapshot."""
        params = {"project": project, "person": person, "meeting": meeting}
        return self.request("GET", "/metrics", params=params)

    def recommendations(
        self,
        *,
        project: str | None = None,
        person: str | None = None,
        meeting: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return prioritised, evidence-backed recommendations."""
        params = {
            "project": project,
            "person": person,
            "meeting": meeting,
            "limit": limit,
            "offset": offset,
        }
        return self.request("GET", "/recommendations", params=params)

    def report(
        self,
        *,
        fmt: str = "markdown",
        project: str | None = None,
        person: str | None = None,
        meeting: list[str] | None = None,
    ) -> dict[str, Any]:
        """Render the full organizational-intelligence report."""
        params = {"format": fmt, "project": project, "person": person, "meeting": meeting}
        return self.request("GET", "/reports", params=params)

    # --- automation ------------------------------------------------------

    def run_pipeline(
        self,
        *,
        config: str | Path | None = None,
        pipeline: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run a declarative pipeline by server-side path or inline mapping."""
        body: dict[str, Any] = {"dry_run": dry_run}
        if config is not None:
            body["config"] = str(config)
        if pipeline is not None:
            body["pipeline"] = pipeline
        return self.request("POST", "/automation/run", json=body)

    def jobs(self, *, limit: int | None = None, offset: int = 0) -> dict[str, Any]:
        """Return recorded automation runs."""
        return self.request("GET", "/automation/jobs", params={"limit": limit, "offset": offset})

    def logs(
        self,
        *,
        correlation_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return structured automation logs."""
        params = {"correlation_id": correlation_id, "limit": limit, "offset": offset}
        return self.request("GET", "/automation/logs", params=params)
