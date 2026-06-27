"""Unit tests for the transcript loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meeting_memory.exceptions import TranscriptLoadError, UnsupportedFormatError
from meeting_memory.io import RawTranscript, TranscriptLoader, load_transcript


def test_load_txt(tmp_path: Path) -> None:
    path = tmp_path / "meeting.txt"
    path.write_text("Alice: hello", encoding="utf-8")
    raw = load_transcript(path)
    assert isinstance(raw, RawTranscript)
    assert raw.content == "Alice: hello"
    assert raw.source_format == "txt"
    assert raw.source_path == str(path)


def test_load_json(tmp_path: Path) -> None:
    path = tmp_path / "meeting.json"
    path.write_text(json.dumps({"utterances": []}), encoding="utf-8")
    raw = load_transcript(path)
    assert raw.content == {"utterances": []}
    assert raw.source_format == "json"


def test_extension_is_case_insensitive(tmp_path: Path) -> None:
    path = tmp_path / "MEETING.TXT"
    path.write_text("Alice: hi", encoding="utf-8")
    assert load_transcript(path).source_format == "txt"


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "meeting.md"
    path.write_text("content", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        load_transcript(path)


def test_missing_extension(tmp_path: Path) -> None:
    path = tmp_path / "meeting"
    path.write_text("content", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        load_transcript(path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(TranscriptLoadError, match="not found"):
        load_transcript(tmp_path / "absent.txt")


def test_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid", encoding="utf-8")
    with pytest.raises(TranscriptLoadError, match="Invalid JSON"):
        load_transcript(path)


def test_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "binary.txt"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(TranscriptLoadError, match="UTF-8"):
        load_transcript(path)


def test_read_error_on_directory(tmp_path: Path) -> None:
    directory = tmp_path / "meeting.txt"
    directory.mkdir()
    with pytest.raises(TranscriptLoadError, match="Could not read"):
        load_transcript(directory)


def test_supported_formats_default() -> None:
    assert TranscriptLoader().supported_formats() == ("json", "txt")


def test_register_custom_format(tmp_path: Path) -> None:
    loader = TranscriptLoader()
    loader.register(".log", lambda text: text.upper())
    assert "log" in loader.supported_formats()
    path = tmp_path / "meeting.log"
    path.write_text("hello", encoding="utf-8")
    assert loader.load(path).content == "HELLO"
