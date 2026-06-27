"""Context assembly for retrieved memories.

Each memory records the index of the utterance it came from. To show *why* a
memory exists, the assembler re-parses the meeting's source transcript and
returns the surrounding utterances (a configurable window before and after the
matching utterance). Parsing is deterministic; results are cached per meeting so
multiple memories from one meeting reparse it only once. If the source is missing
or unreadable, the window degrades gracefully to just the memory's own text.
"""

from __future__ import annotations

from ..exceptions import MeetingMemoryError
from ..models import Utterance
from ..parser import MeetingParser
from ..storage import StoredMeeting, StoredMemory
from .models import ContextUtterance, ContextWindow


class ContextAssembler:
    """Build :class:`ContextWindow` objects by re-reading meeting sources."""

    def __init__(self, parser: MeetingParser | None = None) -> None:
        self._parser = parser or MeetingParser()
        self._cache: dict[str, tuple[Utterance, ...] | None] = {}

    def assemble(
        self, memory: StoredMemory, meeting: StoredMeeting | None, size: int
    ) -> ContextWindow:
        """Return the context window of ``size`` utterances around ``memory``."""
        window = max(0, size)
        utterances = self._utterances(meeting)
        index = memory.utterance_index
        if utterances is None or not 0 <= index < len(utterances):
            target = ContextUtterance(
                index=index, speaker=memory.speaker, text=memory.text, is_match=True
            )
            return ContextWindow(target=target)

        low = max(0, index - window)
        high = min(len(utterances), index + window + 1)
        before = tuple(_to_context(utterances[pos]) for pos in range(low, index))
        after = tuple(_to_context(utterances[pos]) for pos in range(index + 1, high))
        target = _to_context(utterances[index], is_match=True)
        return ContextWindow(before=before, target=target, after=after)

    def _utterances(self, meeting: StoredMeeting | None) -> tuple[Utterance, ...] | None:
        if meeting is None or not meeting.source:
            return None
        if meeting.meeting_id in self._cache:
            return self._cache[meeting.meeting_id]
        utterances: tuple[Utterance, ...] | None
        try:
            utterances = self._parser.parse_file(meeting.source).utterances
        except (MeetingMemoryError, OSError):
            utterances = None
        self._cache[meeting.meeting_id] = utterances
        return utterances


def _to_context(utterance: Utterance, is_match: bool = False) -> ContextUtterance:
    return ContextUtterance(
        index=utterance.index,
        speaker=utterance.speaker.name,
        text=utterance.text,
        is_match=is_match,
    )
