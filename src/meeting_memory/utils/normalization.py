"""Text normalization helpers.

These functions clean up the *form* of transcript text (whitespace, line
endings, speaker labels, timestamp formatting) without altering its semantic
content. They are pure, side-effect-free, and safe to compose.
"""

from __future__ import annotations

import re

from ..models import Timestamp

_WHITESPACE_RE = re.compile(r"\s+")
_LABEL_WRAPPERS = "*_\"'`"


def normalize_newlines(text: str) -> str:
    """Convert Windows (``\\r\\n``) and classic Mac (``\\r``) endings to ``\\n``."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_whitespace(text: str) -> str:
    """Collapse all runs of whitespace into single spaces and strip the ends.

    Intended for a single logical unit of text (such as one utterance), where
    interior newlines and repeated spaces carry no meaning.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_transcript_text(text: str) -> str:
    """Normalize a whole transcript's line structure for stable parsing.

    Line endings are unified, trailing whitespace is removed from every line,
    and leading/trailing blank lines are trimmed. Interior blank lines are
    preserved so that block boundaries remain intact.
    """
    normalized = normalize_newlines(text)
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip("\n")


def normalize_speaker_label(label: str) -> str:
    """Normalize a speaker label without changing its identity.

    Surrounding markdown/quote wrappers, a trailing colon, and redundant
    interior whitespace are removed; the original casing is preserved.
    """
    cleaned = _WHITESPACE_RE.sub(" ", label.strip())
    cleaned = cleaned.rstrip(":").strip()
    return cleaned.strip(_LABEL_WRAPPERS).strip()


def normalize_timestamp(raw: str) -> str:
    """Return the canonical ``HH:MM:SS`` form of a textual timestamp.

    Raises:
        MalformedTranscriptError: If ``raw`` is not a recognised timestamp.
    """
    return Timestamp.parse(raw).label
