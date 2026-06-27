"""Reusable helpers: normalization and transcript statistics."""

from __future__ import annotations

from .normalization import (
    normalize_newlines,
    normalize_speaker_label,
    normalize_timestamp,
    normalize_transcript_text,
    normalize_whitespace,
)
from .statistics import (
    TranscriptStatistics,
    compute_statistics,
    meeting_duration,
    speaker_count,
    speaker_utterance_counts,
    speaker_word_counts,
    utterance_count,
    word_count,
)

__all__ = [
    "TranscriptStatistics",
    "compute_statistics",
    "meeting_duration",
    "normalize_newlines",
    "normalize_speaker_label",
    "normalize_timestamp",
    "normalize_transcript_text",
    "normalize_whitespace",
    "speaker_count",
    "speaker_utterance_counts",
    "speaker_word_counts",
    "utterance_count",
    "word_count",
]
