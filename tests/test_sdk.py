"""Tests for the Python SDK in local and HTTP modes (Phase 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_helpers import EXAMPLES_HISTORY, running_server, seed_db
from meeting_memory.sdk import APIError, MeetingMemoryClient


@pytest.fixture
def local_client(tmp_path: Path) -> MeetingMemoryClient:
    """A seeded local-mode SDK client."""
    db = tmp_path / "atlas.db"
    seed_db(db)
    return MeetingMemoryClient.local(db)


def test_constructor_requires_exactly_one_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        MeetingMemoryClient()
    with pytest.raises(ValueError):
        MeetingMemoryClient(db=tmp_path / "x.db", base_url="http://x")


def test_import_file_and_directory(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    with MeetingMemoryClient.local(db) as client:
        assert client.mode == "local"
        single = client.import_file(EXAMPLES_HISTORY / "meeting1.txt")
        assert single["meetings_imported"] == 1
        bulk = client.import_directory(EXAMPLES_HISTORY, recursive=True)
        assert bulk["status"] in {"success", "partial"}


def test_local_read_surface(local_client: MeetingMemoryClient) -> None:
    with local_client as client:
        assert client.health()["status"] == "ok"
        assert client.version()["version"]
        assert client.stats()["meetings"] == 4
        meetings = client.meetings(limit=2)
        assert meetings["pagination"]["count"] == 2
        meeting_id = meetings["items"][0]["meeting_id"]
        assert client.get_meeting(meeting_id)["meeting_id"] == meeting_id
        memories = client.memories(memory_type=["decision"], limit=3)
        assert all(m["memory_type"] == "decision" for m in memories["items"])
        memory_id = memories["items"][0]["memory_id"]
        assert client.get_memory(memory_id)["memory_id"] == memory_id
        assert client.search("postgres")["stats"]["returned"] >= 1


def test_local_graph_and_intelligence(local_client: MeetingMemoryClient) -> None:
    with local_client as client:
        graph = client.graph(limit=5)
        assert graph["nodes"] > 0
        node_id = graph["listed"][0]["node_id"]
        neighbors = client.neighbors(node_id, depth=2)
        related = [n["node_id"] for n in neighbors["nodes"] if n["node_id"] != node_id]
        if related:
            assert client.path(node_id, related[0], depth=4)["found"] is True
        assert client.insights()["pagination"]["total"] >= 0
        assert 0.0 <= client.metrics()["overall"] <= 1.0
        assert client.recommendations()["pagination"]["total"] >= 0
        assert client.report(fmt="markdown")["content"].startswith("#")


def test_local_automation(local_client: MeetingMemoryClient) -> None:
    with local_client as client:
        run = client.run_pipeline(
            pipeline={"name": "t", "steps": [{"type": "graph"}, {"type": "intelligence"}]}
        )
        assert run["status"] == "success"
        assert client.jobs()["pagination"]["total"] == 1
        assert client.logs()["pagination"]["total"] >= 1
        cid = run["correlation_id"]
        assert client.logs(correlation_id=cid)["pagination"]["total"] >= 1


def test_local_error(local_client: MeetingMemoryClient) -> None:
    with local_client as client:
        with pytest.raises(APIError) as excinfo:
            client.get_memory("missing")
        assert excinfo.value.status_code == 404
        assert excinfo.value.error == "MemoryNotFoundError"


def test_api_error_from_non_dict_payload() -> None:
    error = APIError.from_payload(500, "boom")
    assert error.status_code == 500
    assert "boom" in error.detail


def test_http_mode(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with running_server(db) as base_url, MeetingMemoryClient.connect(base_url) as client:
        assert client.mode == "http"
        assert client.health()["status"] == "ok"
        assert client.meetings()["pagination"]["total"] == 4
        assert client.search("postgres")["stats"]["returned"] >= 1
        assert client.graph()["nodes"] > 0
        assert client.insights()["pagination"]["total"] >= 0
        with pytest.raises(APIError) as excinfo:
            client.get_meeting("missing")
        assert excinfo.value.status_code == 404
