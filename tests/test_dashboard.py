"""Tests for the server-rendered web dashboard (Phase 8)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from api_helpers import make_client, seed_db


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    """A TestClient bound to a seeded database with one automation run."""
    db = tmp_path_factory.mktemp("dash") / "atlas.db"
    seed_db(db)
    test_client = make_client(db)
    with test_client as bound:
        bound.post(
            "/automation/run",
            json={"pipeline": {"name": "t", "steps": [{"type": "graph"}]}},
        )
        yield bound


def test_root_redirects_to_dashboard(client: Any) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {307, 308}
    assert response.headers["location"] == "/dashboard"


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard",
        "/dashboard/meetings",
        "/dashboard/search",
        "/dashboard/search?q=postgres",
        "/dashboard/graph",
        "/dashboard/insights",
        "/dashboard/reports",
        "/dashboard/jobs",
    ],
)
def test_dashboard_pages_render_html(client: Any, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text
    assert "Meeting Memory" in response.text


def test_dashboard_search_shows_results(client: Any) -> None:
    response = client.get("/dashboard/search?q=postgres")
    assert "result(s)" in response.text


def test_dashboard_jobs_lists_run(client: Any) -> None:
    response = client.get("/dashboard/jobs")
    assert "Automation runs" in response.text
    assert "success" in response.text


def test_dashboard_empty_state(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"
    test_client = make_client(db)
    with test_client as bound:
        assert "No data." in bound.get("/dashboard/jobs").text
