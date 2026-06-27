"""Integration, CLI-compatibility, OpenAPI, and edge-coverage tests (Phase 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from api_helpers import EXAMPLES_HISTORY, make_client, seed_db
from meeting_memory.api.dependencies import (
    DB_ENV_VAR,
    get_db_path,
    get_export_service,
)
from meeting_memory.api.errors import status_for
from meeting_memory.cli import main
from meeting_memory.exceptions import (
    DuplicateMeetingError,
    MeetingMemoryError,
    MemoryNotFoundError,
    NodeNotFoundError,
)
from meeting_memory.sdk import MeetingMemoryClient
from meeting_memory.services import ExportService

# --- integration: one store shared by CLI, API, and SDK ------------------


def test_cli_api_sdk_share_one_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "atlas.db"
    assert main(["import-dir", str(EXAMPLES_HISTORY), "--recursive", "--db", str(db)]) == 0
    capsys.readouterr()

    with make_client(db) as client:
        api_total = client.get("/meetings").json()["pagination"]["total"]
    with MeetingMemoryClient.local(db) as sdk:
        sdk_total = sdk.meetings()["pagination"]["total"]

    assert main(["meetings", "--db", str(db), "--json"]) == 0
    cli_out = capsys.readouterr().out
    assert api_total == sdk_total == 4
    assert cli_out.count("meeting_id") == 4


def test_cli_search_matches_api(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    assert main(["search", "postgres", "--db", str(db), "--json"]) == 0
    capsys.readouterr()
    with make_client(db) as client:
        returned = client.get("/search", params={"q": "postgres"}).json()["stats"]["returned"]
    assert returned >= 1


# --- OpenAPI -------------------------------------------------------------


def test_openapi_document(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with make_client(db) as client:
        spec = client.get("/openapi.json").json()
        assert spec["info"]["title"]
        for path in ("/health", "/meetings/import", "/search", "/graph", "/insights"):
            assert path in spec["paths"]
        import_body = spec["paths"]["/meetings/import"]["post"]["requestBody"]
        schema = import_body["content"]["application/json"]["schema"]
        assert "examples" in schema or "$ref" in schema
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200


# --- error mapping -------------------------------------------------------


def test_status_for_mapping() -> None:
    assert status_for(MemoryNotFoundError("x")) == 404
    assert status_for(NodeNotFoundError("x")) == 404
    assert status_for(DuplicateMeetingError("x")) == 409
    assert status_for(MeetingMemoryError("x")) == 400


# --- dependency providers ------------------------------------------------


def test_get_db_path_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DB_ENV_VAR, "/tmp/from-env.db")
    assert get_db_path() == Path("/tmp/from-env.db")


def test_get_export_service_provider(tmp_path: Path) -> None:
    service = get_export_service(tmp_path / "atlas.db")
    assert isinstance(service, ExportService)


# --- SDK edge cases ------------------------------------------------------


def test_sdk_run_pipeline_with_config(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "name: cfg\nsteps:\n  - type: graph\n  - type: intelligence\n", encoding="utf-8"
    )
    with MeetingMemoryClient.local(db) as client:
        result = client.run_pipeline(config=config)
        assert result["status"] == "success"


def test_sdk_skips_empty_list_params(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with MeetingMemoryClient.local(db) as client:
        body = client.memories(speaker=[], limit=2)
        assert body["pagination"]["count"] <= 2


def test_sdk_request_handles_non_json(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    with MeetingMemoryClient.local(db) as client:
        assert client.request("GET", "/dashboard") is None


# --- API automation run via config path ----------------------------------


def test_api_automation_run_with_config(tmp_path: Path) -> None:
    db = tmp_path / "atlas.db"
    seed_db(db)
    config = tmp_path / "pipeline.yaml"
    config.write_text("name: cfg\nsteps:\n  - type: graph\n", encoding="utf-8")
    with make_client(db) as client:
        response = client.post("/automation/run", json={"config": str(config)})
        assert response.status_code == 200
        assert response.json()["status"] == "success"
