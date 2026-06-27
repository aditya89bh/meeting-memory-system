"""Immutable data carriers for the replay engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..storage import StoredMeeting, StoredMemory


@dataclass(frozen=True)
class ReplayFilter:
    """A deterministic selection of meetings to replay.

    All populated fields are combined with logical AND. ``project`` and
    ``person`` are matched case-insensitively against meeting titles, memory
    text, participants, and speakers.
    """

    project: str | None = None
    person: str | None = None
    date: str | None = None
    date_from: str | None = None
    date_to: str | None = None

    def describe(self) -> str:
        """Return a short, human-readable description of the filter."""
        parts: list[str] = []
        if self.project is not None:
            parts.append(f"project={self.project}")
        if self.person is not None:
            parts.append(f"person={self.person}")
        if self.date is not None:
            parts.append(f"date={self.date}")
        if self.date_from is not None:
            parts.append(f"from={self.date_from}")
        if self.date_to is not None:
            parts.append(f"to={self.date_to}")
        return ", ".join(parts) if parts else "all meetings"

    def to_dict(self) -> dict[str, object]:
        """Serialise the filter into JSON-compatible primitives."""
        return {
            "project": self.project,
            "person": self.person,
            "date": self.date,
            "date_from": self.date_from,
            "date_to": self.date_to,
        }


@dataclass(frozen=True)
class ReplayEvent:
    """A single replay step: one meeting and the memories it contributed."""

    index: int
    meeting: StoredMeeting
    memories: tuple[StoredMemory, ...]
    cumulative_memories: int
    cumulative_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def date(self) -> str | None:
        """Return the meeting date (``YYYY-MM-DD``) if known."""
        return self.meeting.date

    def to_dict(self) -> dict[str, object]:
        """Serialise the event into JSON-compatible primitives."""
        return {
            "index": self.index,
            "meeting_id": self.meeting.meeting_id,
            "title": self.meeting.title,
            "date": self.meeting.date,
            "memories": len(self.memories),
            "cumulative_memories": self.cumulative_memories,
            "cumulative_by_type": dict(self.cumulative_by_type),
        }


@dataclass(frozen=True)
class ReplayTimeline:
    """An ordered, reconstructed timeline of replay events."""

    events: tuple[ReplayEvent, ...]
    filter: ReplayFilter

    @property
    def meeting_count(self) -> int:
        """Return the number of meetings in the timeline."""
        return len(self.events)

    @property
    def memory_count(self) -> int:
        """Return the total number of memories across the timeline."""
        return self.events[-1].cumulative_memories if self.events else 0

    @property
    def date_range(self) -> tuple[str | None, str | None]:
        """Return the (earliest, latest) meeting dates, ignoring unknown dates."""
        dates = [event.meeting.date for event in self.events if event.meeting.date]
        if not dates:
            return (None, None)
        return (dates[0], dates[-1])

    def to_dict(self) -> dict[str, object]:
        """Serialise the timeline into JSON-compatible primitives."""
        start, end = self.date_range
        return {
            "filter": self.filter.to_dict(),
            "meeting_count": self.meeting_count,
            "memory_count": self.memory_count,
            "date_range": {"start": start, "end": end},
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class ReplayResult:
    """The outcome of a completed (or partial) replay run."""

    timeline: ReplayTimeline
    steps_played: int
    elapsed_seconds: float
    speed: float
    final_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def memories_played(self) -> int:
        """Return the number of memories surfaced across the played steps."""
        played = self.timeline.events[: self.steps_played]
        return played[-1].cumulative_memories if played else 0

    def to_dict(self) -> dict[str, object]:
        """Serialise the result into JSON-compatible primitives."""
        return {
            "filter": self.timeline.filter.to_dict(),
            "steps_played": self.steps_played,
            "meetings": self.timeline.meeting_count,
            "memories_played": self.memories_played,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "speed": self.speed,
            "final_by_type": dict(self.final_by_type),
        }
