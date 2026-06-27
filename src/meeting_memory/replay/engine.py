"""The replay engine: reconstruct timelines and drive replay sessions."""

from __future__ import annotations

from pathlib import Path

from ..storage import SQLiteMemoryStore, StoredMeeting, StoredMemory
from .models import ReplayEvent, ReplayFilter, ReplayResult, ReplayTimeline
from .session import ReplaySession


class ReplayEngine:
    """Read-only engine that reconstructs and replays meeting timelines."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    # -- timeline construction -------------------------------------------------

    def _load(self) -> list[tuple[StoredMeeting, list[StoredMemory]]]:
        with SQLiteMemoryStore(self.db) as store:
            meetings = store.list_meetings()
            return [(meeting, store.find_by_meeting(meeting.meeting_id)) for meeting in meetings]

    @staticmethod
    def _matches(
        meeting: StoredMeeting,
        memories: list[StoredMemory],
        flt: ReplayFilter,
    ) -> bool:
        if flt.date is not None and meeting.date != flt.date:
            return False
        if flt.date_from is not None and (meeting.date is None or meeting.date < flt.date_from):
            return False
        if flt.date_to is not None and (meeting.date is None or meeting.date > flt.date_to):
            return False
        if flt.project is not None:
            needle = flt.project.lower()
            title = (meeting.title or "").lower()
            if needle not in title and not any(needle in mem.text.lower() for mem in memories):
                return False
        if flt.person is not None:
            needle = flt.person.lower()
            participants = {person.lower() for person in meeting.participants}
            speakers = {(mem.speaker or "").lower() for mem in memories}
            if needle not in participants and needle not in speakers:
                return False
        return True

    def timeline(self, flt: ReplayFilter | None = None) -> ReplayTimeline:
        """Reconstruct a deterministic, chronologically ordered timeline."""
        flt = flt or ReplayFilter()
        selected = [
            (meeting, memories)
            for meeting, memories in self._load()
            if self._matches(meeting, memories, flt)
        ]
        selected.sort(key=lambda pair: (pair[0].date or "", pair[0].meeting_id))

        events: list[ReplayEvent] = []
        cumulative = 0
        by_type: dict[str, int] = {}
        for index, (meeting, memories) in enumerate(selected):
            ordered = tuple(sorted(memories, key=lambda mem: (mem.utterance_index, mem.memory_id)))
            cumulative += len(ordered)
            for memory in ordered:
                by_type[memory.memory_type] = by_type.get(memory.memory_type, 0) + 1
            events.append(
                ReplayEvent(
                    index=index,
                    meeting=meeting,
                    memories=ordered,
                    cumulative_memories=cumulative,
                    cumulative_by_type=dict(by_type),
                )
            )
        return ReplayTimeline(events=tuple(events), filter=flt)

    # -- session / replay drivers ----------------------------------------------

    def session(
        self,
        flt: ReplayFilter | None = None,
        *,
        speed: float = 1.0,
        step_delay: float = 0.0,
    ) -> ReplaySession:
        """Build a step-by-step replay session for the given filter."""
        return ReplaySession(self.timeline(flt), speed=speed, step_delay=step_delay)

    def replay(
        self,
        flt: ReplayFilter | None = None,
        *,
        speed: float = 1.0,
        step_delay: float = 0.0,
    ) -> ReplayResult:
        """Replay every matching meeting and return the result."""
        return self.session(flt, speed=speed, step_delay=step_delay).run()

    def replay_all(self, *, speed: float = 1.0, step_delay: float = 0.0) -> ReplayResult:
        """Replay every stored meeting in chronological order."""
        return self.replay(ReplayFilter(), speed=speed, step_delay=step_delay)

    def replay_project(
        self, project: str, *, speed: float = 1.0, step_delay: float = 0.0
    ) -> ReplayResult:
        """Replay meetings belonging to a single project."""
        return self.replay(ReplayFilter(project=project), speed=speed, step_delay=step_delay)

    def replay_person(
        self, person: str, *, speed: float = 1.0, step_delay: float = 0.0
    ) -> ReplayResult:
        """Replay meetings that involve a single person."""
        return self.replay(ReplayFilter(person=person), speed=speed, step_delay=step_delay)

    def replay_date(
        self, date: str, *, speed: float = 1.0, step_delay: float = 0.0
    ) -> ReplayResult:
        """Replay meetings held on a single date (``YYYY-MM-DD``)."""
        return self.replay(ReplayFilter(date=date), speed=speed, step_delay=step_delay)

    def replay_range(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        *,
        speed: float = 1.0,
        step_delay: float = 0.0,
    ) -> ReplayResult:
        """Replay meetings held within an inclusive date range."""
        flt = ReplayFilter(date_from=date_from, date_to=date_to)
        return self.replay(flt, speed=speed, step_delay=step_delay)
