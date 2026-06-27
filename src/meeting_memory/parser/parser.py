"""Parsing of raw transcript content into structured :class:`Meeting` objects.

Two input shapes are supported out of the box:

* **Plain text** -- line-oriented transcripts where each turn looks like
  ``Speaker: text`` with an optional leading or trailing timestamp. Lines that
  do not begin a new turn are treated as continuations of the previous turn.
  An optional ``---`` delimited front-matter block may carry metadata.
* **JSON** -- a structured object with an ``utterances`` array (or a bare array
  of utterance objects), plus optional ``title``/``date``/``metadata`` fields.

Parsing is purely structural: it produces a faithful, normalized representation
and raises :class:`MalformedTranscriptError` on structurally invalid input. It
performs no semantic validation (see :mod:`meeting_memory.parser.validation`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ..exceptions import MalformedTranscriptError
from ..io import RawTranscript, load_transcript
from ..models import Meeting, Metadata, Speaker, Timestamp, Utterance
from ..utils import (
    normalize_speaker_label,
    normalize_transcript_text,
    normalize_whitespace,
)

_TS = r"\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?"
_LEADING_TS_RE = re.compile(rf"^\s*(?:\[\s*({_TS})\s*\]|\(\s*({_TS})\s*\)|({_TS}))\s+(.*)$")
_TRAILING_TS_RE = re.compile(rf"^(.*?)\s*(?:\[\s*({_TS})\s*\]|\(\s*({_TS})\s*\)|({_TS}))\s*$")

_MAX_SPEAKER_WORDS = 6
_MAX_SPEAKER_CHARS = 50

# Field name aliases accepted in JSON utterance objects.
_SPEAKER_KEYS = ("speaker", "name", "speaker_name")
_TEXT_KEYS = ("text", "utterance", "content", "message")
_TIMESTAMP_KEYS = ("timestamp", "time", "start")


@dataclass
class _Turn:
    """Mutable accumulator for a single turn while scanning text lines."""

    speaker_raw: str
    timestamp_raw: str | None
    text_parts: list[str] = field(default_factory=list)


def _looks_like_speaker(head: str) -> bool:
    """Heuristic deciding whether ``head`` (text before ``:``) names a speaker."""
    if not head:
        return False
    if len(head) > _MAX_SPEAKER_CHARS:
        return False
    return len(head.split()) <= _MAX_SPEAKER_WORDS


def _find_delimiter(rest: str) -> int:
    """Index of the speaker/text separating colon, or ``-1`` if there is none.

    Colons that sit between two digits (as in ``00:01:23``) are skipped so that
    timestamps embedded in the line are never mistaken for the delimiter.
    """
    for index, char in enumerate(rest):
        if char != ":":
            continue
        prev_char = rest[index - 1] if index > 0 else ""
        next_char = rest[index + 1] if index + 1 < len(rest) else ""
        if not (prev_char.isdigit() and next_char.isdigit()):
            return index
    return -1


def _split_turn(line: str) -> tuple[str, str | None, str] | None:
    """Split a line into ``(speaker_raw, timestamp_raw, text)`` if it is a turn.

    Returns ``None`` when the line does not start a new turn (and should be
    treated as a continuation of the previous one).
    """
    rest = line
    timestamp_raw: str | None = None

    leading = _LEADING_TS_RE.match(rest)
    if leading is not None:
        timestamp_raw = leading.group(1) or leading.group(2) or leading.group(3)
        rest = leading.group(4)

    delimiter = _find_delimiter(rest)
    if delimiter == -1:
        return None

    head = rest[:delimiter]
    text = rest[delimiter + 1 :]

    if timestamp_raw is None:
        trailing = _TRAILING_TS_RE.match(head)
        if trailing is not None and (trailing.group(2) or trailing.group(3) or trailing.group(4)):
            head = trailing.group(1)
            timestamp_raw = trailing.group(2) or trailing.group(3) or trailing.group(4)

    speaker_raw = head.strip()
    if not _looks_like_speaker(speaker_raw):
        return None

    return speaker_raw, timestamp_raw, text


def _parse_date(value: str) -> date:
    """Parse an ISO-8601 date, raising a transcript error on failure."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MalformedTranscriptError(f"Invalid date {value!r}: expected YYYY-MM-DD") from exc


def _extract_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split an optional ``---`` delimited front-matter block from ``text``.

    Returns a ``(fields, body)`` pair. When no front matter is present the
    fields mapping is empty and ``body`` is the original text.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    fields: dict[str, str] = {}
    for position in range(1, len(lines)):
        line = lines[position]
        if line.strip() == "---":
            return fields, "\n".join(lines[position + 1 :])
        if not line.strip():
            continue
        if ":" not in line:
            raise MalformedTranscriptError(f"Invalid front-matter line: {line!r}")
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()

    raise MalformedTranscriptError("Unterminated front-matter block (missing closing '---')")


def _build_metadata(
    fields: dict[str, str],
    source_path: str | None,
    source_format: str | None,
) -> Metadata:
    """Assemble :class:`Metadata` from raw string fields and source context."""
    extra = dict(fields)
    title = extra.pop("title", None)
    raw_date = extra.pop("date", None)
    meeting_date = _parse_date(raw_date) if raw_date else None
    return Metadata(
        title=title,
        date=meeting_date,
        source_path=source_path,
        source_format=source_format,
        extra=extra,
    )


def _turns_to_meeting(turns: list[_Turn], metadata: Metadata) -> Meeting:
    """Convert accumulated turns into an immutable :class:`Meeting`."""
    aliases: dict[str, set[str]] = {}
    resolved: list[tuple[str, Timestamp | None, str]] = []

    for turn in turns:
        name = normalize_speaker_label(turn.speaker_raw)
        bucket = aliases.setdefault(name, set())
        if turn.speaker_raw.strip() != name:
            bucket.add(turn.speaker_raw.strip())
        timestamp = Timestamp.parse(turn.timestamp_raw) if turn.timestamp_raw else None
        text = normalize_whitespace(" ".join(turn.text_parts))
        resolved.append((name, timestamp, text))

    speakers = {
        name: Speaker(name=name, aliases=frozenset(alias)) for name, alias in aliases.items()
    }
    utterances = tuple(
        Utterance(index=index, speaker=speakers[name], text=text, timestamp=timestamp)
        for index, (name, timestamp, text) in enumerate(resolved)
    )
    return Meeting(utterances=utterances, metadata=metadata)


class MeetingParser:
    """Parses raw transcript content into structured :class:`Meeting` objects."""

    def parse(self, raw: RawTranscript) -> Meeting:
        """Parse a :class:`RawTranscript`, dispatching on its decoded content."""
        content = raw.content
        if isinstance(content, str):
            return self.parse_text(
                content,
                source_path=raw.source_path,
                source_format=raw.source_format,
            )
        if isinstance(content, dict | list):
            return self.parse_json(
                content,
                source_path=raw.source_path,
                source_format=raw.source_format,
            )
        raise MalformedTranscriptError(
            f"Cannot parse transcript content of type {type(content).__name__}"
        )

    def parse_file(self, path: str | Path) -> Meeting:
        """Load a transcript from ``path`` and parse it into a meeting."""
        return self.parse(load_transcript(path))

    def parse_text(
        self,
        text: str,
        *,
        source_path: str | None = None,
        source_format: str | None = "txt",
    ) -> Meeting:
        """Parse a plain-text transcript into a meeting."""
        fields, body = _extract_front_matter(text)
        metadata = _build_metadata(fields, source_path, source_format)

        body = normalize_transcript_text(body)
        turns: list[_Turn] = []
        current: _Turn | None = None

        for line_number, raw_line in enumerate(body.split("\n"), start=1):
            if not raw_line.strip():
                continue
            split = _split_turn(raw_line)
            if split is not None:
                speaker_raw, timestamp_raw, text_part = split
                current = _Turn(speaker_raw=speaker_raw, timestamp_raw=timestamp_raw)
                stripped = text_part.strip()
                if stripped:
                    current.text_parts.append(stripped)
                turns.append(current)
            elif current is not None:
                current.text_parts.append(raw_line.strip())
            else:
                raise MalformedTranscriptError(
                    f"Line {line_number}: expected 'Speaker: text', got {raw_line!r}"
                )

        return _turns_to_meeting(turns, metadata)

    def parse_json(
        self,
        data: object,
        *,
        source_path: str | None = None,
        source_format: str | None = "json",
    ) -> Meeting:
        """Parse a structured JSON transcript into a meeting."""
        if isinstance(data, list):
            raw_utterances: object = data
            fields: dict[str, str] = {}
        elif isinstance(data, dict):
            if "utterances" not in data:
                raise MalformedTranscriptError("JSON transcript is missing 'utterances'")
            raw_utterances = data["utterances"]
            fields = self._json_metadata_fields(data)
        else:
            raise MalformedTranscriptError(
                f"JSON transcript must be an object or array, got {type(data).__name__}"
            )

        if not isinstance(raw_utterances, list):
            raise MalformedTranscriptError("'utterances' must be a JSON array")

        metadata = _build_metadata(fields, source_path, source_format)
        turns = [self._json_turn(item, index) for index, item in enumerate(raw_utterances)]
        return _turns_to_meeting(turns, metadata)

    @staticmethod
    def _json_metadata_fields(data: dict[str, object]) -> dict[str, str]:
        """Collect string metadata fields from a JSON object."""
        fields: dict[str, str] = {}
        for key in ("title", "date"):
            value = data.get(key)
            if value is not None:
                fields[key] = str(value)
        extra = data.get("metadata")
        if isinstance(extra, dict):
            for key, value in extra.items():
                if value is not None:
                    fields[str(key)] = str(value)
        return fields

    @staticmethod
    def _json_turn(item: object, index: int) -> _Turn:
        """Convert a single JSON utterance object into a :class:`_Turn`."""
        if not isinstance(item, dict):
            raise MalformedTranscriptError(
                f"Utterance #{index} must be a JSON object, got {type(item).__name__}"
            )

        speaker = _first_present(item, _SPEAKER_KEYS)
        if speaker is None:
            raise MalformedTranscriptError(f"Utterance #{index} is missing a speaker")

        text = _first_present(item, _TEXT_KEYS)
        if text is None:
            raise MalformedTranscriptError(f"Utterance #{index} is missing text")

        timestamp_raw: str | None = None
        timestamp_value = _first_present(item, _TIMESTAMP_KEYS)
        if isinstance(timestamp_value, bool):
            raise MalformedTranscriptError(f"Utterance #{index} has an invalid timestamp")
        if isinstance(timestamp_value, int | float):
            timestamp_raw = str(Timestamp.from_seconds(float(timestamp_value)).label)
        elif isinstance(timestamp_value, str):
            timestamp_raw = timestamp_value

        return _Turn(speaker_raw=str(speaker), timestamp_raw=timestamp_raw, text_parts=[str(text)])


def _first_present(item: dict[str, object], keys: tuple[str, ...]) -> object | None:
    """Return the first non-``None`` value among ``keys`` in ``item``."""
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


_DEFAULT_PARSER = MeetingParser()


def parse_file(path: str | Path) -> Meeting:
    """Load and parse a transcript file using the shared default parser."""
    return _DEFAULT_PARSER.parse_file(path)


def parse_text(text: str, *, source_path: str | None = None) -> Meeting:
    """Parse plain-text transcript content using the shared default parser."""
    return _DEFAULT_PARSER.parse_text(text, source_path=source_path)


def parse_json(data: object, *, source_path: str | None = None) -> Meeting:
    """Parse structured JSON transcript content using the shared default parser."""
    return _DEFAULT_PARSER.parse_json(data, source_path=source_path)
