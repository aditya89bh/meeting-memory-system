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


class ExtractionError(MeetingMemoryError):
    """Base class for failures in the memory extraction layer."""


class ExtractionValidationError(ExtractionError):
    """Raised when an extracted memory record fails validation."""


class StorageError(MeetingMemoryError):
    """Base class for failures in the persistent storage layer."""


class MemoryNotFoundError(StorageError):
    """Raised when a memory record cannot be found by id."""


class MeetingNotFoundError(StorageError):
    """Raised when a meeting record cannot be found by id."""


class DuplicateMeetingError(StorageError):
    """Raised when a meeting (by id or transcript hash) is already stored."""


class GraphError(StorageError):
    """Base class for failures in the organizational memory graph layer."""


class NodeNotFoundError(GraphError):
    """Raised when a graph node cannot be found by id."""


class ConnectorError(MeetingMemoryError):
    """Base class for failures in the connector and automation layer."""


class ConnectorValidationError(ConnectorError):
    """Raised when a connector request fails pre-flight validation."""


class UnknownConnectorError(ConnectorError):
    """Raised when no connector is registered for a requested source/format."""


class PipelineConfigError(ConnectorError):
    """Raised when a declarative pipeline configuration is invalid."""


class ScheduleError(ConnectorError):
    """Raised when a schedule definition or cron expression is invalid."""


class AutomationError(ConnectorError):
    """Raised when an automation job fails to execute."""


class ReplayError(MeetingMemoryError):
    """Raised when a replay session is misconfigured or exhausted."""


class EmptyMeetingError(ValidationError):
    """Raised when a meeting contains no utterances."""


class DuplicateTimestampError(ValidationError):
    """Raised when two utterances share the same timestamp."""


class InvalidSpeakerError(ValidationError):
    """Raised when an utterance references a missing or invalid speaker."""


__all__ = [
    "AutomationError",
    "ConnectorError",
    "ConnectorValidationError",
    "DuplicateMeetingError",
    "DuplicateTimestampError",
    "EmptyMeetingError",
    "ExtractionError",
    "ExtractionValidationError",
    "GraphError",
    "InvalidSpeakerError",
    "MalformedTranscriptError",
    "MeetingMemoryError",
    "MeetingNotFoundError",
    "MemoryNotFoundError",
    "NodeNotFoundError",
    "PipelineConfigError",
    "ReplayError",
    "ScheduleError",
    "StorageError",
    "TranscriptLoadError",
    "TranscriptParseError",
    "UnknownConnectorError",
    "UnsupportedFormatError",
    "ValidationError",
]
