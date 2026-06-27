"""Shared helpers for Phase 8 service/API/SDK/dashboard tests."""

from __future__ import annotations

import socket
import threading
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from meeting_memory.services import MeetingService

EXAMPLES_HISTORY = Path(__file__).resolve().parents[1] / "examples" / "history"


def seed_db(db: Path) -> None:
    """Import the bundled example transcripts into ``db``."""
    MeetingService(db).import_path(EXAMPLES_HISTORY, recursive=True)


def make_client(db: Path) -> object:
    """Return a Starlette ``TestClient`` bound to an app on ``db``."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient

    from meeting_memory.api.app import create_app

    return TestClient(create_app(db_path=db))


def _free_port() -> int:
    """Return an available localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ThreadedServer:
    """Run a uvicorn server in a background thread for HTTP-mode tests."""

    def __init__(self, app: FastAPI, port: int) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.port = port
        self._thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self) -> None:
        """Start the server thread and block until it is ready."""
        self._thread.start()
        deadline = time.monotonic() + 10.0
        while not self.server.started:
            if time.monotonic() > deadline:  # pragma: no cover - safety valve
                raise RuntimeError("server failed to start in time")
            time.sleep(0.02)

    def stop(self) -> None:
        """Signal the server to exit and join the thread."""
        self.server.should_exit = True
        self._thread.join(timeout=10.0)

    @property
    def base_url(self) -> str:
        """Return the base URL of the running server."""
        return f"http://127.0.0.1:{self.port}"


@contextmanager
def running_server(db: Path) -> Iterator[str]:
    """Yield the base URL of a uvicorn server serving an app bound to ``db``."""
    from meeting_memory.api.app import create_app

    server = ThreadedServer(create_app(db_path=db), _free_port())
    server.start()
    try:
        yield server.base_url
    finally:
        server.stop()
