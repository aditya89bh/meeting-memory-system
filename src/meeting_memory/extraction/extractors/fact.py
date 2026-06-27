"""Extractor for important factual statements.

A "fact" here is a declarative statement carrying project, customer, requirement,
timeline, metric, or constraint information. Because such statements are less
formulaic than, say, decisions, confidence stays modest and is boosted only when
the utterance contains a concrete quantitative signal (a number, percentage,
currency amount, quarter, or year).
"""

from __future__ import annotations

import re
from typing import ClassVar

from ...models import Utterance
from ..confidence import LOW, MEDIUM
from ..models import ExtractedMemory, FactMemory, MemoryType
from .base import ExtractionContext, PhraseExtractor, PhraseRule, make_phrase_rule

_QUANTITATIVE_BOOST = 0.15

# Concrete, factual signals: numbers, percentages, money, quarters, or years.
_QUANTITATIVE_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s?%|\$\s?\d|\b\d+(?:\.\d+)?[kKmMbB]?\b|\bQ[1-4]\b|\b\d{4}\b)"
)


class FactExtractor(PhraseExtractor):
    """Detect factual statements about projects, customers, metrics, constraints."""

    memory_type: ClassVar[MemoryType] = MemoryType.FACT
    memory_class: ClassVar[type[ExtractedMemory]] = FactMemory
    rules: ClassVar[tuple[PhraseRule, ...]] = (
        make_phrase_rule(r"\b(?:customers?|clients?|accounts?)\b", MEDIUM),
        make_phrase_rule(
            r"\brequirements?\b|\bmust (?:support|have|be)\b|\bspec(?:ification)?s?\b", MEDIUM
        ),
        make_phrase_rule(
            r"\bbudget\b|\bconstraints?\b|\bcap(?:ped)?\b|\blimit(?:s|ed|ation)?\b", MEDIUM
        ),
        make_phrase_rule(
            r"\bdeadline\b|\blaunch(?:es|ed|ing)?\b|\brelease\b|\btimeline\b|\bmilestone\b|\bschedule\b",
            MEDIUM,
        ),
        make_phrase_rule(
            r"\brevenue\b|\bgrowth\b|\bchurn\b|\bMRR\b|\bARR\b|\blatency\b|\buptime\b|\bconversion\b|\busers?\b",
            MEDIUM,
        ),
        make_phrase_rule(r"\bprojects?\b|\broadmap\b|\bversions?\b", LOW),
    )

    def extract(self, utterance: Utterance, context: ExtractionContext) -> list[ExtractedMemory]:
        # Questions are handled by the question extractor, not as facts.
        if utterance.text.rstrip().endswith("?"):
            return []
        return super().extract(utterance, context)

    def _confidence_boost(self, utterance: Utterance, match: re.Match[str]) -> float:
        return _QUANTITATIVE_BOOST if _QUANTITATIVE_RE.search(utterance.text) else 0.0
