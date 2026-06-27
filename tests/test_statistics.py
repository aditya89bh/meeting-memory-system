"""Unit tests for transcript statistics."""

from __future__ import annotations

from meeting_memory.parser import parse_text
from meeting_memory.utils import (
    compute_statistics,
    meeting_duration,
    speaker_count,
    speaker_utterance_counts,
    speaker_word_counts,
    utterance_count,
    word_count,
)

SAMPLE = "[00:00:05] Alice: hello there friend\n[00:00:35] Bob: hi\n[00:01:05] Alice: bye now"


def test_utterance_count() -> None:
    assert utterance_count(parse_text(SAMPLE)) == 3


def test_speaker_count() -> None:
    assert speaker_count(parse_text(SAMPLE)) == 2


def test_word_count() -> None:
    assert word_count(parse_text(SAMPLE)) == 6


def test_speaker_utterance_counts() -> None:
    assert speaker_utterance_counts(parse_text(SAMPLE)) == {"Alice": 2, "Bob": 1}


def test_speaker_word_counts() -> None:
    assert speaker_word_counts(parse_text(SAMPLE)) == {"Alice": 5, "Bob": 1}


def test_meeting_duration() -> None:
    assert meeting_duration(parse_text(SAMPLE)) == 60.0


def test_meeting_duration_none_without_timestamps() -> None:
    assert meeting_duration(parse_text("Alice: hi")) is None


def test_compute_statistics_to_dict() -> None:
    stats = compute_statistics(parse_text(SAMPLE))
    assert stats.to_dict() == {
        "utterance_count": 3,
        "speaker_count": 2,
        "word_count": 6,
        "duration_seconds": 60.0,
        "speaker_utterance_counts": {"Alice": 2, "Bob": 1},
        "speaker_word_counts": {"Alice": 5, "Bob": 1},
    }
