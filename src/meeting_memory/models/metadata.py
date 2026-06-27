"""Metadata model describing a meeting's provenance and context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Metadata:
    """Contextual information about a meeting.

    Attributes:
        title: Human-readable meeting title, if known.
        date: Calendar date on which the meeting took place, if known.
        source_path: Filesystem path the transcript was loaded from, if any.
        source_format: Format identifier of the source (e.g. ``"txt"``).
        extra: Arbitrary additional key/value pairs from the source.
    """

    title: str | None = None
    date: date | None = None
    source_path: str | None = None
    source_format: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialise the metadata into JSON-compatible primitives."""
        return {
            "title": self.title,
            "date": self.date.isoformat() if self.date else None,
            "source_path": self.source_path,
            "source_format": self.source_format,
            "extra": dict(self.extra),
        }
