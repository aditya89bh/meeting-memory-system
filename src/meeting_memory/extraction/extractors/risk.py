"""Extractor for risks, concerns, blockers, and dependencies."""

from __future__ import annotations

from typing import ClassVar

from ..confidence import HIGH, MEDIUM, MEDIUM_HIGH
from ..models import ExtractedMemory, MemoryType, RiskMemory
from .base import PhraseExtractor, PhraseRule, make_phrase_rule


class RiskExtractor(PhraseExtractor):
    """Detect risk language: risk, concern, blocker, dependency, delay, ..."""

    memory_type: ClassVar[MemoryType] = MemoryType.RISK
    memory_class: ClassVar[type[ExtractedMemory]] = RiskMemory
    rules: ClassVar[tuple[PhraseRule, ...]] = (
        make_phrase_rule(r"\bblock(?:er|ed|ing)\b", HIGH),
        make_phrase_rule(r"\b(?:might|may|could) fail\b", HIGH),
        make_phrase_rule(r"\brisk(?:s|y)?\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bconcern(?:s|ed)?\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bdepend(?:s|ency|encies|ent)\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bdelay(?:s|ed|ing)?\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bbottleneck\b", MEDIUM),
    )
