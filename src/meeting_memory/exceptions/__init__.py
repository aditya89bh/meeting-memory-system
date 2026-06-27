"""Exception hierarchy for the Meeting Memory System.

All errors raised by the library inherit from :class:`MeetingMemoryError`, which
makes it possible to catch any library-specific failure with a single
``except`` clause while still allowing callers to handle individual error
categories (loading, parsing, validation) when they need finer control.
"""

from __future__ import annotations


class MeetingMemoryError(Exception):
    """Base class for every error raised by the Meeting Memory System."""


class TranscriptLoadError(MeetingMemoryError):
    """Raised when a transcript file cannot be read from disk."""


class UnsupportedFormatError(TranscriptLoadError):
    """Raised when a transcript file has no registered loader for its format."""


class TranscriptParseError(MeetingMemoryError):
    """Raised when transcript content cannot be parsed into a meeting."""


class MalformedTranscriptError(TranscriptParseError):
    """Raised when transcript content is structurally invalid."""


class ValidationError(MeetingMemoryError):
    """Base class for semantic validation failures on parsed meetings."""


class EmptyMeetingError(ValidationError):
    """Raised when a meeting contains no utterances."""


class DuplicateTimestampError(ValidationError):
    """Raised when two utterances share the same timestamp."""


class InvalidSpeakerError(ValidationError):
    """Raised when an utterance references a missing or invalid speaker."""


__all__ = [
    "DuplicateTimestampError",
    "EmptyMeetingError",
    "InvalidSpeakerError",
    "MalformedTranscriptError",
    "MeetingMemoryError",
    "TranscriptLoadError",
    "TranscriptParseError",
    "UnsupportedFormatError",
    "ValidationError",
]
