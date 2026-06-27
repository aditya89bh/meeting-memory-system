"""Unit tests for the retrieval CLI subcommands: search, timeline, explain."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from meeting_memory.cli import _format_context_lines, _format_ranked, main
from meeting_memory.retrieval import ContextWindow, RankedMemory
from meeting_memory.storage import SQLiteMemoryStore, StoredMemory, import_meeting

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _transcript(title: str, date: str, topic: str) -> str:
    return (
        f"---\ntitle: {title}\ndate: {date}\n---\n"
        f"[00:00:05] Alice: We decided to adopt {topic} for the platform.\n"
        f"[00:00:20] Bob: I will deploy {topic} by Friday.\n"
        f"[00:00:35] Alice: There is a risk that {topic} will fail under load.\n"
    )


def _seed(tmp_path: Path) -> Path:
    db = tmp_path / "db.sqlite"
    with SQLiteMemoryStore(db) as store:
        for name, date, topic in [
            ("jan", "2026-01-05", "postgres"),
            ("feb", "2026-02-10", "postgres"),
            ("mar", "2026-03-15", "redis"),
        ]:
            path = tmp_path / f"{name}.txt"
            path.write_text(_transcript(name, date, topic), encoding="utf-8")
            import_meeting(path, store, now=_NOW)
    return db


def test_search_human_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["search", "redis", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "mar:decision:0" in out
    assert 'keyword "redis"' in out
    assert "jan:" not in out


def test_search_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["search", "postgres", "--db", str(db), "--type", "decision", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stats"]["candidates"] == 2
    assert all(r["memory"]["memory_type"] == "decision" for r in payload["results"])


def test_search_speaker_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["search", "--speaker", "Bob", "--status", "active", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Bob" in out
    assert "Alice" not in out


def test_search_with_context(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["search", "--type", "commitment", "--db", str(db), "--context", "1"]) == 0
    out = capsys.readouterr().out
    assert "context:" in out
    assert "We decided to adopt" in out


def test_search_pagination(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert (
        main(
            [
                "search",
                "--type",
                "decision",
                "--db",
                str(db),
                "--limit",
                "1",
                "--offset",
                "1",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["stats"]["returned"] == 1
    assert payload["stats"]["candidates"] == 3


def test_search_no_results(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["search", "nonexistentword", "--db", str(db)]) == 0
    assert "No matching memories." in capsys.readouterr().out


def test_timeline_human_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["timeline", "--type", "risk", "--db", str(db)]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0].startswith("2026-01-05")
    assert out[-1].startswith("2026-03-15")


def test_timeline_between(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert (
        main(
            [
                "timeline",
                "--type",
                "decision",
                "--between",
                "2026-02-01",
                "2026-03-31",
                "--db",
                str(db),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "feb:decision:0" in out
    assert "mar:decision:0" in out
    assert "jan:decision:0" not in out


def test_timeline_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["timeline", "--type", "risk", "--db", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [r["memory"]["meeting_id"] for r in payload["results"]] == ["jan", "feb", "mar"]


def test_timeline_no_results(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["timeline", "--speaker", "Nobody", "--db", str(db)]) == 0
    assert "No matching memories." in capsys.readouterr().out


def test_explain_human_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["explain", "jan:decision:0", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "id:         jan:decision:0" in out
    assert "matched because:" in out
    assert "speaker Alice" in out
    assert "memory type decision" in out
    assert "context:" in out


def test_explain_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["explain", "jan:risk:2", "--db", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["memory"]["memory_id"] == "jan:risk:2"
    assert payload["explanation"]["reasons"]
    assert payload["context"]["target"]["text"].startswith("There is a risk")


def test_explain_missing_memory_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["explain", "does:not:exist", "--db", str(db)]) == 1
    assert "error:" in capsys.readouterr().err


def test_search_after_and_before_filters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _seed(tmp_path)
    assert (
        main(["search", "--type", "decision", "--after", "2026-03-01", "--db", str(db), "--json"])
        == 0
    )
    after = json.loads(capsys.readouterr().out)
    assert [r["memory"]["meeting_id"] for r in after["results"]] == ["mar"]
    assert (
        main(["search", "--type", "decision", "--before", "2026-01-31", "--db", str(db), "--json"])
        == 0
    )
    before = json.loads(capsys.readouterr().out)
    assert [r["memory"]["meeting_id"] for r in before["results"]] == ["jan"]


def _bare_memory() -> StoredMemory:
    return StoredMemory(
        memory_id="m:decision:0",
        meeting_id="m",
        memory_type="decision",
        text="we adopt postgres",
        confidence=0.9,
        utterance_index=0,
        content_hash="h",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def test_format_ranked_without_explanation_or_context() -> None:
    ranked = RankedMemory(memory=_bare_memory(), score=0.5)
    lines = _format_ranked(ranked, context_size=1)
    assert len(lines) == 1
    assert lines[0].startswith("m:decision:0")


def test_format_context_lines_without_target() -> None:
    assert _format_context_lines(ContextWindow()) == []
