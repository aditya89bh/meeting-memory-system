"""Unit tests for the ``meeting-memory extract`` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meeting_memory.cli import main

_TRANSCRIPT = "\n".join(
    [
        "Alice: We decided to use Postgres.",
        "Bob: I will send the plan by Friday.",
        "Carol: There is a risk the migration could slip.",
        "Dave: Should we ship this?",
    ]
)
_NOW = "2026-01-15T09:00:00+00:00"


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _extract(tmp_path: Path, *args: str) -> Path:
    return _write(tmp_path, "meeting.txt", _TRANSCRIPT)


def test_extract_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _extract(tmp_path)
    assert main(["extract", str(path), "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["meeting_id"] == "meeting"
    assert payload["total"] == 4
    assert set(payload["counts"]) == {"decision", "commitment", "risk", "question"}
    assert set(payload["memories"]) == {"decision", "commitment", "risk", "question"}
    assert payload["warnings"] == []


def test_extract_json_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    utterances = [{"speaker": "A", "text": "We decided to adopt Postgres."}]
    path = _write(tmp_path, "m.json", json.dumps({"utterances": utterances}))
    assert main(["extract", str(path), "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"] == {"decision": 1}


def test_filter_by_type(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _extract(tmp_path)
    assert main(["extract", str(path), "--types", "decision,commitment", "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["counts"]) == {"decision", "commitment"}


def test_min_confidence_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _extract(tmp_path)
    assert main(["extract", str(path), "--min-confidence", "0.9", "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    for items in payload["memories"].values():
        for memory in items:
            assert memory["confidence"] >= 0.9


def test_no_deduplicate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "dup.txt", "Alice: We decided to ship.\nBob: We decided to ship.")
    assert main(["extract", str(path), "--no-deduplicate", "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["decision"] == 2


def test_output_to_file(tmp_path: Path) -> None:
    path = _extract(tmp_path)
    out = tmp_path / "result.json"
    assert main(["extract", str(path), "--output", str(out), "--now", _NOW]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["total"] == 4


def test_compact_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _extract(tmp_path)
    assert main(["extract", str(path), "--indent", "0", "--now", _NOW]) == 0
    out = capsys.readouterr().out
    assert "\n  " not in out


def test_now_is_stamped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _extract(tmp_path)
    assert main(["extract", str(path), "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    decision = payload["memories"]["decision"][0]
    assert decision["extracted_at"] == _NOW


def test_no_memory_meeting(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "quiet.txt", "Alice: Good morning.\nBob: Hello.")
    assert main(["extract", str(path), "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 0
    assert payload["counts"] == {}
    assert payload["memories"] == {}


def test_missing_file_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["extract", str(tmp_path / "absent.txt")]) == 1
    assert "error:" in capsys.readouterr().err


def test_unknown_type_is_rejected(tmp_path: Path) -> None:
    path = _extract(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(["extract", str(path), "--types", "bogus"])
    assert excinfo.value.code == 2


def test_types_ignores_empty_tokens(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _extract(tmp_path)
    assert main(["extract", str(path), "--types", "decision,", "--now", _NOW]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["counts"]) == {"decision"}


def test_types_all_empty_is_rejected(tmp_path: Path) -> None:
    path = _extract(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(["extract", str(path), "--types", " , "])
    assert excinfo.value.code == 2


def test_out_of_range_confidence_is_rejected(tmp_path: Path) -> None:
    path = _extract(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(["extract", str(path), "--min-confidence", "1.5"])
    assert excinfo.value.code == 2


def test_invalid_now_is_rejected(tmp_path: Path) -> None:
    path = _extract(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(["extract", str(path), "--now", "not-a-date"])
    assert excinfo.value.code == 2


def test_parse_command_still_works(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _extract(tmp_path)
    assert main(["parse", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "utterances" in payload
    assert "memories" not in payload
