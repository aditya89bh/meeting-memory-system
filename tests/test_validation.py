"""Unit tests for meeting validation."""

from __future__ import annotations

import pytest

from meeting_memory.exceptions import (
    DuplicateTimestampError,
    EmptyMeetingError,
    InvalidSpeakerError,
)
from meeting_memory.models import Meeting, Speaker, Timestamp, Utterance
from meeting_memory.parser import (
    parse_json,
    validate_meeting,
    validate_not_empty,
    validate_speakers,
    validate_unique_timestamps,
)


def test_validate_not_empty_raises() -> None:
    with pytest.raises(EmptyMeetingError):
        validate_not_empty(Meeting())


def test_validate_not_empty_passes() -> None:
    meeting = parse_json([{"speaker": "A", "text": "x"}])
    validate_not_empty(meeting)


def test_validate_speakers_detects_blank() -> None:
    meeting = Meeting(utterances=(Utterance(0, Speaker("   "), "x"),))
    with pytest.raises(InvalidSpeakerError, match="Utterance 0"):
        validate_speakers(meeting)


def test_validate_unique_timestamps_detects_duplicate() -> None:
    meeting = Meeting(
        utterances=(
            Utterance(0, Speaker("A"), "x", Timestamp.from_seconds(5)),
            Utterance(1, Speaker("B"), "y", Timestamp.from_seconds(5)),
        )
    )
    with pytest.raises(DuplicateTimestampError, match="00:00:05"):
        validate_unique_timestamps(meeting)


def test_validate_unique_timestamps_ignores_missing() -> None:
    meeting = Meeting(
        utterances=(
            Utterance(0, Speaker("A"), "x"),
            Utterance(1, Speaker("B"), "y"),
        )
    )
    validate_unique_timestamps(meeting)


def test_validate_meeting_returns_same_instance() -> None:
    meeting = parse_json([{"speaker": "A", "text": "x"}])
    assert validate_meeting(meeting) is meeting


def test_validate_meeting_allows_duplicates_when_relaxed() -> None:
    meeting = parse_json(
        [
            {"speaker": "A", "text": "x", "timestamp": 5},
            {"speaker": "B", "text": "y", "timestamp": 5},
        ]
    )
    assert validate_meeting(meeting, require_timestamps_unique=False) is meeting
    with pytest.raises(DuplicateTimestampError):
        validate_meeting(meeting)
