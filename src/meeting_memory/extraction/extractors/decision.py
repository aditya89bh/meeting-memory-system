"""Extractor for decisions the group settled on."""

from __future__ import annotations

from typing import ClassVar

from ..confidence import HIGH, MEDIUM_HIGH, VERY_HIGH
from ..models import DecisionMemory, ExtractedMemory, MemoryType
from .base import PhraseExtractor, PhraseRule, make_phrase_rule


class DecisionExtractor(PhraseExtractor):
    """Detect explicit decision language such as "we decided" or "approved"."""

    memory_type: ClassVar[MemoryType] = MemoryType.DECISION
    memory_class: ClassVar[type[ExtractedMemory]] = DecisionMemory
    rules: ClassVar[tuple[PhraseRule, ...]] = (
        make_phrase_rule(r"\bwe(?:'ve| have| had)? decided\b", VERY_HIGH),
        make_phrase_rule(r"\bwe agreed\b", HIGH),
        make_phrase_rule(r"\b(?:the |final )?decision is\b", HIGH),
        make_phrase_rule(r"\bfinal call(?: is)?\b", HIGH),
        make_phrase_rule(r"\blet'?s go with\b", HIGH),
        make_phrase_rule(r"\bapproved\b", HIGH),
        make_phrase_rule(r"\bwe will use\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bwe'?ll go with\b", MEDIUM_HIGH),
    )
