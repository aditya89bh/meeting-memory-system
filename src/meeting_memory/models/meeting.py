"""Meeting model aggregating utterances, speakers and metadata."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .metadata import Metadata
from .timestamp import Timestamp
from .utterance import Utterance


@dataclass(frozen=True)
class Meeting:
    """A fully parsed meeting.

    A meeting is an ordered sequence of :class:`Utterance` objects together with
    :class:`Metadata`. Speakers are derived from the utterances to guarantee the
    two never drift out of sync.
    """

    utterances: tuple[Utterance, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=Metadata)

    @property
    def speakers(self) -> tuple[str, ...]:
        """Unique speaker names in order of first appearance."""
        seen: dict[str, None] = {}
        for utterance in self.utterances:
            seen.setdefault(utterance.speaker.name, None)
        return tuple(seen)

    @property
    def start(self) -> Timestamp | None:
        """Earliest timestamp in the meeting, if any utterance is timestamped."""
        stamps = [u.timestamp for u in self.utterances if u.timestamp is not None]
        return min(stamps) if stamps else None

    @property
    def end(self) -> Timestamp | None:
        """Latest timestamp in the meeting, if any utterance is timestamped."""
        stamps = [u.timestamp for u in self.utterances if u.timestamp is not None]
        return max(stamps) if stamps else None

    def __len__(self) -> int:
        return len(self.utterances)

    def __iter__(self) -> Iterator[Utterance]:
        return iter(self.utterances)

    def to_dict(self) -> dict[str, object]:
        """Serialise the meeting into JSON-compatible primitives."""
        return {
            "metadata": self.metadata.to_dict(),
            "speakers": list(self.speakers),
            "utterances": [utterance.to_dict() for utterance in self.utterances],
        }
