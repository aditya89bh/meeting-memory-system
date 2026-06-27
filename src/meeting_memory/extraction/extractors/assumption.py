"""Extractor for assumptions the discussion relied on."""

from __future__ import annotations

from typing import ClassVar

from ..confidence import HIGH, MEDIUM, MEDIUM_HIGH, VERY_HIGH
from ..models import AssumptionMemory, ExtractedMemory, MemoryType
from .base import PhraseExtractor, PhraseRule, make_phrase_rule


class AssumptionExtractor(PhraseExtractor):
    """Detect assumption language: assuming, we assume, if this holds, ..."""

    memory_type: ClassVar[MemoryType] = MemoryType.ASSUMPTION
    memory_class: ClassVar[type[ExtractedMemory]] = AssumptionMemory
    rules: ClassVar[tuple[PhraseRule, ...]] = (
        make_phrase_rule(r"\bbased on the assumption\b", VERY_HIGH),
        make_phrase_rule(r"\bwe(?:'re| are)? assum(?:e|ing)\b", HIGH),
        make_phrase_rule(r"\bassum(?:e|es|ing|ption)\b", HIGH),
        make_phrase_rule(r"\bif this holds\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bpresumably\b", MEDIUM),
    )
