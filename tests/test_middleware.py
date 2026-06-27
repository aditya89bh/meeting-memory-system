"""Tests for API middleware: correlation ids, timing, logging, headers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from api_helpers import make_client, seed_db
from meeting_memory.api.errors import CORRELATION_HEADER
from meeting_memory.api.middleware import PROCESS_TIME_HEADER, VERSION_HEADER


def test_response_carries_observability_headers(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with make_client(db) as client:
        response = client.get("/health")
        assert response.headers[CORRELATION_HEADER]
        assert response.headers[VERSION_HEADER]
        float(response.headers[PROCESS_TIME_HEADER])


def test_correlation_id_is_propagated(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with make_client(db) as client:
        response = client.get("/health", headers={CORRELATION_HEADER: "fixed-id-123"})
        assert response.headers[CORRELATION_HEADER] == "fixed-id-123"


def test_minted_correlation_ids_differ(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with make_client(db) as client:
        first = client.get("/health").headers[CORRELATION_HEADER]
        second = client.get("/health").headers[CORRELATION_HEADER]
        assert first != second


def test_error_response_includes_correlation_id(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with make_client(db) as client:
        response = client.get("/meetings/nope", headers={CORRELATION_HEADER: "err-id"})
        assert response.status_code == 404
        assert response.headers[CORRELATION_HEADER] == "err-id"
        assert response.json()["correlation_id"] == "err-id"


def test_request_is_logged_structured(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with make_client(db) as client, caplog.at_level(logging.INFO, logger="meeting_memory.api"):
        client.get("/health")
    records = [r for r in caplog.records if r.name == "meeting_memory.api"]
    assert records
    payload = json.loads(records[-1].getMessage())
    assert payload["event"] == "request"
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert "correlation_id" in payload
