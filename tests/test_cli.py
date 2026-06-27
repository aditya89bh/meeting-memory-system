"""Unit tests for the command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meeting_memory.cli import main


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_txt_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "m.txt", "Alice: hello world\nBob: hi")
    assert main(["parse", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["speakers"] == ["Alice", "Bob"]
    assert "statistics" not in payload


def test_parse_with_stats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "m.txt", "Alice: hello world\nBob: hi there")
    assert main(["parse", str(path), "--stats"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["statistics"]["utterance_count"] == 2
    assert payload["statistics"]["speaker_count"] == 2


def test_parse_json_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    content = json.dumps({"utterances": [{"speaker": "A", "text": "x"}]})
    path = _write(tmp_path, "m.json", content)
    assert main(["parse", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["speakers"] == ["A"]


def test_output_to_file(tmp_path: Path) -> None:
    path = _write(tmp_path, "m.txt", "Alice: hi")
    out = tmp_path / "out.json"
    assert main(["parse", str(path), "--output", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["speakers"] == ["Alice"]


def test_compact_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "m.txt", "Alice: hi")
    assert main(["parse", str(path), "--indent", "0"]) == 0
    out = capsys.readouterr().out
    assert "\n  " not in out


def test_missing_file_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["parse", str(tmp_path / "absent.txt")]) == 1
    assert "error:" in capsys.readouterr().err


def test_empty_meeting_fails_validation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "empty.txt", "   \n\n")
    assert main(["parse", str(path)]) == 1
    assert "no utterances" in capsys.readouterr().err


def test_no_validate_allows_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "empty.txt", "")
    assert main(["parse", str(path), "--no-validate"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["utterances"] == []


def test_duplicate_timestamps_error_and_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = json.dumps(
        {
            "utterances": [
                {"speaker": "A", "text": "x", "timestamp": 5},
                {"speaker": "B", "text": "y", "timestamp": 5},
            ]
        }
    )
    path = _write(tmp_path, "dup.json", content)
    assert main(["parse", str(path)]) == 1
    assert "Duplicate timestamp" in capsys.readouterr().err
    assert main(["parse", str(path), "--allow-duplicate-timestamps"]) == 0


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "meeting-memory" in capsys.readouterr().out


def test_no_command_errors() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code != 0
