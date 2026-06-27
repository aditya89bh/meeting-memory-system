"""Utterance model representing a single contribution by a speaker."""

from __future__ import annotations

from dataclasses import dataclass

from .speaker import Speaker
from .timestamp import Timestamp


@dataclass(frozen=True)
class Utterance:
    """A single, ordered contribution made by a speaker during a meeting.

    Attributes:
        index: Zero-based position of the utterance within the meeting.
        speaker: The participant who produced the utterance.
        text: The spoken content, already normalized by the parser.
        timestamp: The start time of the utterance, when available.
    """

    index: int
    speaker: Speaker
    text: str
    timestamp: Timestamp | None = None

    @property
    def word_count(self) -> int:
        """Number of whitespace-delimited words in the utterance text."""
        return len(self.text.split())

    def to_dict(self) -> dict[str, object]:
        """Serialise the utterance into JSON-compatible primitives."""
        return {
            "index": self.index,
            "speaker": self.speaker.name,
            "text": self.text,
            "timestamp": self.timestamp.to_dict() if self.timestamp else None,
        }
