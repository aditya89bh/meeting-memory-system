"""Unit tests for the persistent-storage CLI subcommands."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from meeting_memory.cli import main
from meeting_memory.storage import MemoryStatus, SQLiteMemoryStore, import_meeting

_TRANSCRIPT = "\n".join(
    [
        "---",
        "title: Atlas Sync",
        "date: 2026-02-02",
        "---",
        "Alice: We decided to adopt Postgres.",
        "Bob: I will send the report by Friday.",
        "Alice: There is a risk the migration fails.",
    ]
)
_NOW = "2026-01-01T00:00:00+00:00"


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    transcript = tmp_path / "atlas.txt"
    transcript.write_text(_TRANSCRIPT, encoding="utf-8")
    return transcript, tmp_path / "db.sqlite"


def _import(tmp_path: Path) -> tuple[Path, Path]:
    """Seed a database via the library so the CLI capture stays clean."""
    transcript, db = _setup(tmp_path)
    with SQLiteMemoryStore(db) as store:
        import_meeting(transcript, store, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    return transcript, db


def test_import_prints_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    transcript, db = _setup(tmp_path)
    assert main(["import", str(transcript), "--db", str(db), "--now", _NOW]) == 0
    out = capsys.readouterr().out
    assert "Meeting imported: atlas" in out
    assert "3 memories stored" in out
    assert db.exists()


def test_import_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    transcript, db = _setup(tmp_path)
    assert main(["import", str(transcript), "--db", str(db), "--now", _NOW, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stored_count"] == 3
    assert payload["meeting"]["meeting_id"] == "atlas"


def test_list_human_and_filters(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, db = _import(tmp_path)
    assert main(["list", "--db", str(db)]) == 0
    assert "atlas:decision:0" in capsys.readouterr().out
    assert main(["list", "--db", str(db), "--type", "risk"]) == 0
    out = capsys.readouterr().out
    assert "atlas:risk:2" in out
    assert "decision" not in out
    assert main(["list", "--db", str(db), "--speaker", "Bob", "--limit", "5"]) == 0
    assert "Bob" in capsys.readouterr().out
    assert main(["list", "--db", str(db), "--status", "active", "--min-confidence", "0.9"]) == 0
    assert "atlas:decision:0" in capsys.readouterr().out
    assert main(["list", "--db", str(db), "--meeting", "atlas"]) == 0
    assert "atlas:risk:2" in capsys.readouterr().out


def test_list_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, db = _import(tmp_path)
    assert main(["list", "--db", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {item["memory_type"] for item in payload} == {"decision", "commitment", "risk"}


def test_list_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty.db"
    assert main(["list", "--db", str(db)]) == 0
    assert capsys.readouterr().out.strip() == "No memories found."


def test_show_human_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, db = _import(tmp_path)
    assert main(["show", "atlas:decision:0", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "id:         atlas:decision:0" in out
    assert "meta.trigger:" in out
    assert "evidence:" in out
    assert main(["show", "atlas:decision:0", "--db", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["memory_id"] == "atlas:decision:0"


def test_show_superseded_pointer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, db = _import(tmp_path)
    store = SQLiteMemoryStore(db)
    store.supersede("atlas:decision:0", "atlas:risk:2")
    store.close()
    assert main(["show", "atlas:decision:0", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "superseded_by: atlas:risk:2" in out


def test_show_missing_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, db = _import(tmp_path)
    assert main(["show", "ghost", "--db", str(db)]) == 1
    assert "error:" in capsys.readouterr().err


def test_meetings_human_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, db = _import(tmp_path)
    assert main(["meetings", "--db", str(db)]) == 0
    assert "atlas" in capsys.readouterr().out
    assert main(["meetings", "--db", str(db), "--json", "--limit", "5"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["meeting_id"] == "atlas"


def test_meetings_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "empty.db"
    assert main(["meetings", "--db", str(db)]) == 0
    assert capsys.readouterr().out.strip() == "No meetings found."


def test_stats_human_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, db = _import(tmp_path)
    assert main(["stats", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Meetings: 1" in out
    assert "decision: 1" in out
    assert "active: 3" in out
    assert main(["stats", "--db", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["meetings"] == 1
    assert payload["by_type"]["risk"] == 1
    assert payload["by_status"][MemoryStatus.ACTIVE.value] == 3


def test_invalid_status_argument_exits(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    with pytest.raises(SystemExit):
        main(["list", "--db", str(db), "--status", "bogus"])


def test_invalid_type_argument_exits(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    with pytest.raises(SystemExit):
        main(["list", "--db", str(db), "--type", "bogus"])


def test_empty_str_set_argument_exits(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    with pytest.raises(SystemExit):
        main(["list", "--db", str(db), "--speaker", " , "])


def test_empty_status_set_argument_exits(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    with pytest.raises(SystemExit):
        main(["list", "--db", str(db), "--status", " , "])
