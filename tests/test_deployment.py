"""Tests for deployment artifacts and the health-probe script (Phase 9)."""

from __future__ import annotations

import importlib.util
import json
import os
import urllib.error
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_healthcheck() -> ModuleType:
    """Load the standalone health-probe script as a module."""
    path = ROOT / "scripts" / "healthcheck.py"
    spec = importlib.util.spec_from_file_location("mm_healthcheck", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    """Minimal stand-in for an ``http.client.HTTPResponse``."""

    def __init__(self, status: int, payload: dict[str, object]) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


# -- Dockerfile / Compose -----------------------------------------------------


def test_dockerfile_is_complete() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim AS build" in text
    assert "python -m build --wheel" in text
    assert "HEALTHCHECK" in text
    assert "USER appuser" in text
    assert "EXPOSE 8000" in text
    assert 'ENTRYPOINT ["/app/scripts/start.sh"]' in text


def test_dockerignore_excludes_artifacts() -> None:
    text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".venv" in text
    assert "*.db" in text


def test_compose_files_have_service_and_volume() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "meeting-memory:" in compose
    assert "MEETING_MEMORY_DB" in compose
    assert "healthcheck:" in compose
    assert "8000:8000" in compose
    assert "meeting-memory-data:" in compose
    prod = (ROOT / "examples/ops/deployment/docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "image: meeting-memory:" in prod


def test_start_script_is_executable_and_configurable() -> None:
    path = ROOT / "scripts" / "start.sh"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env sh")
    assert "uvicorn meeting_memory.api.app:app" in text
    assert "MEETING_MEMORY_PORT" in text
    assert os.access(path, os.X_OK)


# -- healthcheck.py -----------------------------------------------------------


def test_healthcheck_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_healthcheck()
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: FakeResponse(200, {"status": "ok", "version": "1"}),
    )
    assert module.main() == 0


def test_healthcheck_unhealthy_status(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_healthcheck()
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: FakeResponse(200, {"status": "degraded"}),
    )
    assert module.main() == 1


def test_healthcheck_bad_status_code(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_healthcheck()
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: FakeResponse(503, {"status": "ok"}),
    )
    assert module.main() == 1


def test_healthcheck_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_healthcheck()

    def boom(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(module.urllib.request, "urlopen", boom)
    assert module.main() == 1


def test_healthcheck_rewrites_bind_all_host(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_healthcheck()
    seen: list[str] = []

    def capture(url: str, *args: object, **kwargs: object) -> FakeResponse:
        seen.append(url)
        return FakeResponse(200, {"status": "ok"})

    monkeypatch.setenv("MEETING_MEMORY_HOST", "0.0.0.0")
    monkeypatch.setattr(module.urllib.request, "urlopen", capture)
    assert module.main() == 0
    assert seen and "127.0.0.1" in seen[0]
