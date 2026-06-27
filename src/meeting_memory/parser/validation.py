"""Semantic validation of parsed :class:`Meeting` objects.

Structural problems (e.g. a line that cannot be parsed) are reported by the
parser as :class:`MalformedTranscriptError`. The validators here operate one
level higher: they check that an already-parsed meeting is internally coherent
-- it has content, every utterance has a real speaker, and timestamps do not
collide. Each check raises a specific, descriptive subclass of
:class:`ValidationError`.
"""

from __future__ import annotations

from ..exceptions import (
    DuplicateTimestampError,
    EmptyMeetingError,
    InvalidSpeakerError,
)
from ..models import Meeting


def validate_not_empty(meeting: Meeting) -> None:
    """Ensure the meeting contains at least one utterance.

    Raises:
        EmptyMeetingError: If the meeting has no utterances.
    """
    if len(meeting) == 0:
        raise EmptyMeetingError("Meeting contains no utterances")


def validate_speakers(meeting: Meeting) -> None:
    """Ensure every utterance is attributed to a named speaker.

    Raises:
        InvalidSpeakerError: If any utterance has a blank speaker name.
    """
    for utterance in meeting:
        if not utterance.speaker.is_named:
            raise InvalidSpeakerError(
                f"Utterance {utterance.index} has an empty or whitespace speaker name"
            )


def validate_unique_timestamps(meeting: Meeting) -> None:
    """Ensure no two utterances share the same timestamp.

    Utterances without a timestamp are ignored.

    Raises:
        DuplicateTimestampError: If two utterances have identical timestamps.
    """
    seen: dict[float, int] = {}
    for utterance in meeting:
        if utterance.timestamp is None:
            continue
        seconds = utterance.timestamp.total_seconds
        previous = seen.get(seconds)
        if previous is not None:
            raise DuplicateTimestampError(
                f"Duplicate timestamp {utterance.timestamp.label} shared by "
                f"utterances {previous} and {utterance.index}"
            )
        seen[seconds] = utterance.index


def validate_meeting(meeting: Meeting, *, require_timestamps_unique: bool = True) -> Meeting:
    """Run all validators and return the meeting unchanged when it is valid.

    Args:
        meeting: The parsed meeting to validate.
        require_timestamps_unique: When ``True`` (the default), duplicate
            timestamps are treated as an error.

    Returns:
        The same ``meeting`` instance, enabling fluent ``validate_meeting(...)``
        usage.

    Raises:
        ValidationError: If any individual validator fails.
    """
    validate_not_empty(meeting)
    validate_speakers(meeting)
    if require_timestamps_unique:
        validate_unique_timestamps(meeting)
    return meeting
