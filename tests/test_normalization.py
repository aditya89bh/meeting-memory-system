"""Unit tests for the normalization helpers."""

from __future__ import annotations

import pytest

from meeting_memory.exceptions import MalformedTranscriptError
from meeting_memory.utils import (
    normalize_newlines,
    normalize_speaker_label,
    normalize_timestamp,
    normalize_transcript_text,
    normalize_whitespace,
)


def test_normalize_newlines() -> None:
    assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_normalize_whitespace_collapses_and_strips() -> None:
    assert normalize_whitespace("  a   b\n\t c ") == "a b c"


def test_normalize_transcript_text_trims_lines_and_edges() -> None:
    raw = "\r\n  first  \r\n\r\nsecond   \r\n\r\n"
    assert normalize_transcript_text(raw) == "  first\n\nsecond"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  **Alice B.** :", "Alice B."),
        ("*Bob*", "Bob"),
        ("Carol:", "Carol"),
        ('  "Dave"  ', "Dave"),
        ("Eve", "Eve"),
        ("Alice   Smith", "Alice Smith"),
    ],
)
def test_normalize_speaker_label(raw: str, expected: str) -> None:
    assert normalize_speaker_label(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1:2:3", "01:02:03"),
        ("[00:05]", "00:00:05"),
        ("90", "00:01:30"),
    ],
)
def test_normalize_timestamp(raw: str, expected: str) -> None:
    assert normalize_timestamp(raw) == expected


def test_normalize_timestamp_rejects_invalid() -> None:
    with pytest.raises(MalformedTranscriptError):
        normalize_timestamp("not-a-time")
