"""Transcript loading from disk with an extensible, format-aware registry.

The loader is intentionally decoupled from the parser: its only job is to read a
file and decode it into an in-memory structure (a string for plain text, a
parsed object for JSON). Adding support for a new on-disk format is a matter of
registering a small reader callable; no parser changes are required.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..exceptions import TranscriptLoadError, UnsupportedFormatError

# A reader turns the raw textual contents of a file into an in-memory structure.
FormatReader = Callable[[str], object]


@dataclass(frozen=True)
class RawTranscript:
    """The decoded contents of a transcript file, prior to parsing.

    Attributes:
        content: Decoded payload. ``str`` for text formats, a parsed object
            (typically ``dict`` or ``list``) for structured formats.
        source_format: Normalised format identifier, e.g. ``"txt"`` or ``"json"``.
        source_path: Absolute path the transcript was read from.
    """

    content: object
    source_format: str
    source_path: str


def _read_text(text: str) -> object:
    """Reader for plain-text transcripts: pass the contents through unchanged."""
    return text


def _read_json(text: str) -> object:
    """Reader for JSON transcripts: decode into Python objects."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise TranscriptLoadError(f"Invalid JSON transcript: {exc}") from exc


class TranscriptLoader:
    """Loads transcripts from disk, dispatching on file extension.

    New formats can be registered at runtime via :meth:`register`, keeping the
    loader open for extension without modification.
    """

    def __init__(self) -> None:
        self._readers: dict[str, FormatReader] = {}
        self.register("txt", _read_text)
        self.register("json", _read_json)

    def register(self, extension: str, reader: FormatReader) -> None:
        """Register ``reader`` for files with the given ``extension``.

        The extension is matched case-insensitively and without a leading dot.
        """
        self._readers[extension.lower().lstrip(".")] = reader

    def supported_formats(self) -> tuple[str, ...]:
        """Return the registered format identifiers in sorted order."""
        return tuple(sorted(self._readers))

    def load(self, path: str | Path) -> RawTranscript:
        """Load and decode the transcript at ``path``.

        Raises:
            UnsupportedFormatError: If no reader is registered for the extension.
            TranscriptLoadError: If the file cannot be read or decoded.
        """
        file_path = Path(path)
        extension = file_path.suffix.lower().lstrip(".")

        if not extension:
            raise UnsupportedFormatError(
                f"Cannot determine format for {file_path} (no file extension); "
                f"supported formats: {', '.join(self.supported_formats())}"
            )
        reader = self._readers.get(extension)
        if reader is None:
            raise UnsupportedFormatError(
                f"Unsupported transcript format {extension!r}; "
                f"supported formats: {', '.join(self.supported_formats())}"
            )

        try:
            text = file_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise TranscriptLoadError(f"Transcript file not found: {file_path}") from exc
        except OSError as exc:
            raise TranscriptLoadError(f"Could not read transcript {file_path}: {exc}") from exc
        except UnicodeDecodeError as exc:
            raise TranscriptLoadError(f"Transcript {file_path} is not valid UTF-8: {exc}") from exc

        return RawTranscript(
            content=reader(text),
            source_format=extension,
            source_path=str(file_path),
        )


_DEFAULT_LOADER = TranscriptLoader()


def load_transcript(path: str | Path) -> RawTranscript:
    """Load a transcript using the shared default :class:`TranscriptLoader`."""
    return _DEFAULT_LOADER.load(path)
