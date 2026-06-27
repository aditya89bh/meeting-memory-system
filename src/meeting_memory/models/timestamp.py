"""Timestamp model representing a position within a meeting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..exceptions import MalformedTranscriptError

# Matches ``HH:MM:SS``, ``MM:SS`` and ``SS`` with an optional fractional part,
# tolerating surrounding whitespace and square brackets, e.g. ``[00:01:23.5]``.
_TIMESTAMP_RE = re.compile(
    r"""
    ^\s*[\[(]?\s*
    (?:
        (?:(?P<hours>\d+):)?(?P<minutes>[0-5]?\d):(?P<seconds>[0-5]?\d)
        |
        (?P<only_seconds>\d+)
    )
    (?:[.,](?P<fraction>\d+))?
    \s*[\])]?\s*$
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, order=True)
class Timestamp:
    """A point in time within a meeting, measured in seconds from its start.

    Ordering and equality are based solely on :attr:`total_seconds`; the
    :attr:`raw` label is preserved for provenance but ignored in comparisons.
    """

    total_seconds: float
    raw: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.total_seconds < 0:
            raise MalformedTranscriptError(f"Timestamp cannot be negative: {self.total_seconds!r}")

    @classmethod
    def from_seconds(cls, total_seconds: float, raw: str | None = None) -> Timestamp:
        """Create a timestamp from an absolute number of seconds."""
        return cls(total_seconds=float(total_seconds), raw=raw)

    @classmethod
    def parse(cls, value: str) -> Timestamp:
        """Parse a textual timestamp into a :class:`Timestamp`.

        Supported forms include ``HH:MM:SS``, ``MM:SS`` and a bare second count,
        each optionally wrapped in square brackets and optionally carrying a
        fractional component (``.`` or ``,`` separated).

        Raises:
            MalformedTranscriptError: If ``value`` is not a recognised format.
        """
        match = _TIMESTAMP_RE.match(value)
        if match is None:
            raise MalformedTranscriptError(f"Unrecognised timestamp format: {value!r}")

        if match.group("only_seconds") is not None:
            total = float(match.group("only_seconds"))
        else:
            hours = int(match.group("hours") or 0)
            minutes = int(match.group("minutes"))
            seconds = int(match.group("seconds"))
            total = float(hours * 3600 + minutes * 60 + seconds)

        fraction = match.group("fraction")
        if fraction:
            total += float(f"0.{fraction}")

        return cls(total_seconds=total, raw=value.strip())

    @property
    def label(self) -> str:
        """Canonical ``HH:MM:SS`` (or ``HH:MM:SS.mmm``) string representation."""
        total = self.total_seconds
        hours, remainder = divmod(int(total), 3600)
        minutes, seconds = divmod(remainder, 60)
        base = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        fractional = total - int(total)
        if fractional:
            millis = round(fractional * 1000)
            return f"{base}.{millis:03d}"
        return base

    def to_dict(self) -> dict[str, float | str]:
        """Serialise the timestamp into JSON-compatible primitives."""
        return {"total_seconds": self.total_seconds, "label": self.label}

    def __str__(self) -> str:
        return self.label
