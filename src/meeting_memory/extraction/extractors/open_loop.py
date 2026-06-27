"""Extractor for open loops: unresolved threads needing future attention."""

from __future__ import annotations

from typing import ClassVar

from ..confidence import HIGH, MEDIUM, MEDIUM_HIGH
from ..models import ExtractedMemory, MemoryType, OpenLoopMemory
from .base import PhraseExtractor, PhraseRule, make_phrase_rule


class OpenLoopExtractor(PhraseExtractor):
    """Detect explicit "still unresolved" markers (pending, follow-up, TBD, ...).

    Note: detecting *genuinely unanswered questions* requires cross-utterance
    reasoning that is out of scope for this deterministic phase; only explicit
    open-loop language is matched here.
    """

    memory_type: ClassVar[MemoryType] = MemoryType.OPEN_LOOP
    memory_class: ClassVar[type[ExtractedMemory]] = OpenLoopMemory
    rules: ClassVar[tuple[PhraseRule, ...]] = (
        make_phrase_rule(r"\bneeds? to (?:be )?decide(?:d)?\b", HIGH),
        make_phrase_rule(r"\bto be (?:confirmed|decided|determined)\b", HIGH),
        make_phrase_rule(r"\b(?:not resolved|unresolved)\b", HIGH),
        make_phrase_rule(r"\bTBD\b", HIGH),
        make_phrase_rule(r"\bopen question\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bstill open\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bfollow[ -]?up\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bcircle back\b", MEDIUM),
        make_phrase_rule(r"\bpending\b", MEDIUM),
    )
