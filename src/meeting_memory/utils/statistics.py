"""Descriptive statistics for parsed meetings.

These helpers are pure read-only computations over a :class:`Meeting`; they never
mutate their input. :func:`compute_statistics` bundles the individual metrics
into a single serialisable summary.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..models import Meeting


def utterance_count(meeting: Meeting) -> int:
    """Total number of utterances in the meeting."""
    return len(meeting)


def speaker_count(meeting: Meeting) -> int:
    """Number of distinct speakers in the meeting."""
    return len(meeting.speakers)


def word_count(meeting: Meeting) -> int:
    """Total number of words across every utterance."""
    return sum(utterance.word_count for utterance in meeting)


def speaker_utterance_counts(meeting: Meeting) -> dict[str, int]:
    """Number of utterances per speaker, keyed by speaker name."""
    counter: Counter[str] = Counter(utterance.speaker.name for utterance in meeting)
    return dict(counter)


def speaker_word_counts(meeting: Meeting) -> dict[str, int]:
    """Total words spoken per speaker, keyed by speaker name."""
    counter: Counter[str] = Counter()
    for utterance in meeting:
        counter[utterance.speaker.name] += utterance.word_count
    return dict(counter)


def meeting_duration(meeting: Meeting) -> float | None:
    """Elapsed seconds between the first and last timestamp, if available.

    Returns ``None`` when fewer than two utterances carry timestamps.
    """
    start, end = meeting.start, meeting.end
    if start is None or end is None:
        return None
    return end.total_seconds - start.total_seconds


@dataclass(frozen=True)
class TranscriptStatistics:
    """A bundle of descriptive metrics for a meeting."""

    utterance_count: int
    speaker_count: int
    word_count: int
    duration_seconds: float | None
    speaker_utterance_counts: dict[str, int]
    speaker_word_counts: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        """Serialise the statistics into JSON-compatible primitives."""
        return {
            "utterance_count": self.utterance_count,
            "speaker_count": self.speaker_count,
            "word_count": self.word_count,
            "duration_seconds": self.duration_seconds,
            "speaker_utterance_counts": dict(self.speaker_utterance_counts),
            "speaker_word_counts": dict(self.speaker_word_counts),
        }


def compute_statistics(meeting: Meeting) -> TranscriptStatistics:
    """Compute a full :class:`TranscriptStatistics` summary for the meeting."""
    return TranscriptStatistics(
        utterance_count=utterance_count(meeting),
        speaker_count=speaker_count(meeting),
        word_count=word_count(meeting),
        duration_seconds=meeting_duration(meeting),
        speaker_utterance_counts=speaker_utterance_counts(meeting),
        speaker_word_counts=speaker_word_counts(meeting),
    )
