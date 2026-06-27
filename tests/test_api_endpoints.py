"""Tests for the REST API endpoints (Phase 8)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from api_helpers import make_client, seed_db


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    """A TestClient bound to a seeded database (module-scoped for speed)."""
    db = tmp_path_factory.mktemp("api") / "atlas.db"
    seed_db(db)
    test_client = make_client(db)
    with test_client as bound:
        yield bound


# --- system --------------------------------------------------------------


def test_health_and_version(client: Any) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    version = client.get("/version")
    assert version.json()["name"]


# --- meetings ------------------------------------------------------------


def test_list_meetings_pagination(client: Any) -> None:
    response = client.get("/meetings", params={"limit": 2})
    body = response.json()
    assert body["pagination"]["total"] == 4
    assert body["pagination"]["count"] == 2
    assert len(body["items"]) == 2


def test_meeting_stats(client: Any) -> None:
    body = client.get("/meetings/stats").json()
    assert body["meetings"] == 4
    assert body["memories"] > 0


def test_get_meeting_and_missing(client: Any) -> None:
    meeting_id = client.get("/meetings").json()["items"][0]["meeting_id"]
    assert client.get(f"/meetings/{meeting_id}").json()["meeting_id"] == meeting_id
    missing = client.get("/meetings/nope")
    assert missing.status_code == 404
    assert missing.json()["error"] == "MeetingNotFoundError"


def test_import_inline_and_validation(tmp_path: Path) -> None:
    db = tmp_path / "import.db"
    test_client = make_client(db)
    with test_client as bound:
        created = bound.post(
            "/meetings/import",
            json={"content": "Alice: We decided to ship.\n", "format": "text"},
        )
        assert created.status_code == 201
        assert created.json()["meetings_imported"] == 1
        dry = bound.post(
            "/meetings/import",
            json={"content": "Bob: A risk emerged.\n", "dry_run": True},
        )
        assert dry.json()["dry_run"] is True
        bad = bound.post("/meetings/import", json={})
        assert bad.status_code == 400


# --- memories ------------------------------------------------------------


def test_list_memories_filtered(client: Any) -> None:
    body = client.get("/memories", params={"type": "decision", "limit": 5}).json()
    assert all(item["memory_type"] == "decision" for item in body["items"])
    assert body["pagination"]["total"] >= len(body["items"])


def test_get_memory_and_missing(client: Any) -> None:
    memory_id = client.get("/memories").json()["items"][0]["memory_id"]
    assert client.get(f"/memories/{memory_id}").json()["memory_id"] == memory_id
    assert client.get("/memories/nope").status_code == 404


# --- search --------------------------------------------------------------


def test_search(client: Any) -> None:
    body = client.get("/search", params={"q": "postgres"}).json()
    assert body["stats"]["returned"] >= 1
    assert body["results"][0]["memory"]["text"]


def test_search_validation_error(client: Any) -> None:
    response = client.get("/search", params={"limit": 0})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["errors"]


# --- graph ---------------------------------------------------------------


def test_graph_summary_neighbors_path(client: Any) -> None:
    summary = client.get("/graph", params={"limit": 5}).json()
    assert summary["nodes"] > 0
    node_id = summary["listed"][0]["node_id"]
    neighbors = client.get("/graph/neighbors", params={"node_id": node_id, "depth": 2}).json()
    assert neighbors["node"]["node_id"] == node_id
    related = [n["node_id"] for n in neighbors["nodes"] if n["node_id"] != node_id]
    if related:
        path = client.get(
            "/graph/path", params={"source": node_id, "target": related[0], "depth": 4}
        ).json()
        assert path["found"] is True


def test_graph_path_not_found(client: Any) -> None:
    all_nodes = [n["node_id"] for n in client.get("/graph").json()["listed"]]
    source = all_nodes[0]
    neighbors = client.get("/graph/neighbors", params={"node_id": source, "depth": 1}).json()
    direct = {n["node_id"] for n in neighbors["nodes"]}
    target = next((nid for nid in all_nodes if nid != source and nid not in direct), None)
    if target is not None:
        path = client.get(
            "/graph/path", params={"source": source, "target": target, "depth": 1}
        ).json()
        assert path["found"] is False


# --- intelligence --------------------------------------------------------


def test_insights_metrics_recommendations_reports(client: Any) -> None:
    insights = client.get("/insights", params={"limit": 1}).json()
    assert insights["pagination"]["total"] >= 0
    typed = client.get("/insights", params={"type": "recurring_risk"}).json()
    assert all(i["type"] == "recurring_risk" for i in typed["items"])
    metrics = client.get("/metrics").json()
    assert 0.0 <= metrics["overall"] <= 1.0
    recs = client.get("/recommendations", params={"limit": 1}).json()
    assert recs["pagination"]["total"] >= 0
    for fmt in ("markdown", "json", "text"):
        report = client.get("/reports", params={"format": fmt}).json()
        assert report["format"] == fmt
        assert report["content"]


# --- automation ----------------------------------------------------------


def test_automation_run_jobs_logs(tmp_path: Path) -> None:
    db = tmp_path / "auto.db"
    seed_db(db)
    test_client = make_client(db)
    with test_client as bound:
        run = bound.post(
            "/automation/run",
            json={"pipeline": {"name": "t", "steps": [{"type": "graph"}]}},
        )
        assert run.status_code == 200
        assert run.json()["status"] == "success"
        config_missing = bound.post("/automation/run", json={})
        assert config_missing.status_code == 400
        jobs = bound.get("/automation/jobs").json()
        assert jobs["pagination"]["total"] == 1
        logs = bound.get("/automation/logs").json()
        assert logs["pagination"]["total"] >= 1


# --- errors --------------------------------------------------------------


def test_unknown_route_structured_error(client: Any) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "http_error"
