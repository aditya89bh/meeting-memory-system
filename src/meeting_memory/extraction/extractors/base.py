"""Shared framework for rule-based extractors.

The common pattern is "scan an utterance for trigger phrases and, if any match,
emit a single best memory of this extractor's type". :class:`PhraseExtractor`
implements that pattern so concrete extractors only declare their phrase rules
(and, where needed, extra enrichment such as a commitment's owner/deadline).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable

from ...models import Utterance
from ..confidence import score_for_text
from ..models import EvidenceSpan, ExtractedMemory, MemoryType


@dataclass(frozen=True)
class ExtractionContext:
    """Per-run context shared by every extractor for a single meeting."""

    meeting_id: str
    extracted_at: datetime


@dataclass(frozen=True)
class PhraseRule:
    """A compiled trigger phrase paired with the base confidence it implies."""

    pattern: re.Pattern[str]
    base_confidence: float


def make_phrase_rule(pattern: str, base_confidence: float) -> PhraseRule:
    """Compile ``pattern`` (case-insensitive) into a :class:`PhraseRule`."""
    return PhraseRule(re.compile(pattern, re.IGNORECASE), base_confidence)


def make_memory_id(meeting_id: str, memory_type: MemoryType, utterance_index: int) -> str:
    """Build a deterministic id for a memory.

    Each extractor emits at most one memory per utterance, so the triple of
    meeting, type, and utterance index is unique and stable across runs.
    """
    return f"{meeting_id}:{memory_type.value}:{utterance_index}"


@runtime_checkable
class Extractor(Protocol):
    """Protocol implemented by every extractor."""

    memory_type: ClassVar[MemoryType]

    def extract(self, utterance: Utterance, context: ExtractionContext) -> list[ExtractedMemory]:
        """Return the memories found in ``utterance`` (possibly empty)."""
        ...


@dataclass(frozen=True)
class _MemoryFields:
    """The fields common to every memory, assembled before construction."""

    memory_id: str
    text: str
    meeting_id: str
    utterance_index: int
    evidence: EvidenceSpan
    confidence: float
    speaker: str | None
    extracted_at: datetime
    metadata: dict[str, str]


class PhraseExtractor:
    """Base class for extractors driven by a list of trigger-phrase rules."""

    memory_type: ClassVar[MemoryType]
    memory_class: ClassVar[type[ExtractedMemory]]
    rules: ClassVar[tuple[PhraseRule, ...]]

    def extract(self, utterance: Utterance, context: ExtractionContext) -> list[ExtractedMemory]:
        match = self._best_match(utterance.text)
        if match is None:
            return []
        rule, found = match
        fields = self._fields(utterance, context, rule, found)
        return [self._construct(fields, utterance, found)]

    def _best_match(self, text: str) -> tuple[PhraseRule, re.Match[str]] | None:
        """Return the strongest (then earliest) matching rule for ``text``."""
        best: tuple[PhraseRule, re.Match[str]] | None = None
        for rule in self.rules:
            found = rule.pattern.search(text)
            if found is None:
                continue
            if best is None:
                best = (rule, found)
                continue
            current_rule, current_match = best
            if (rule.base_confidence, -found.start()) > (
                current_rule.base_confidence,
                -current_match.start(),
            ):
                best = (rule, found)
        return best

    def _fields(
        self,
        utterance: Utterance,
        context: ExtractionContext,
        rule: PhraseRule,
        match: re.Match[str],
    ) -> _MemoryFields:
        start, end = match.span()
        evidence = EvidenceSpan(utterance.index, start, end, utterance.text[start:end])
        confidence = score_for_text(
            rule.base_confidence,
            utterance.text,
            boost=self._confidence_boost(utterance, match),
        )
        return _MemoryFields(
            memory_id=make_memory_id(context.meeting_id, self.memory_type, utterance.index),
            text=utterance.text,
            meeting_id=context.meeting_id,
            utterance_index=utterance.index,
            evidence=evidence,
            confidence=confidence,
            speaker=utterance.speaker.name or None,
            extracted_at=context.extracted_at,
            metadata=self._metadata(match),
        )

    def _construct(
        self,
        fields: _MemoryFields,
        utterance: Utterance,
        match: re.Match[str],
    ) -> ExtractedMemory:
        """Build the concrete memory; overridden by extractors with extra fields."""
        return self.memory_class(
            memory_id=fields.memory_id,
            text=fields.text,
            meeting_id=fields.meeting_id,
            utterance_index=fields.utterance_index,
            evidence=fields.evidence,
            confidence=fields.confidence,
            speaker=fields.speaker,
            extracted_at=fields.extracted_at,
            metadata=fields.metadata,
        )

    def _metadata(self, match: re.Match[str]) -> dict[str, str]:
        """Default metadata records the literal trigger phrase that matched."""
        return {"trigger": match.group(0)}

    def _confidence_boost(self, utterance: Utterance, match: re.Match[str]) -> float:
        """Extra confidence for corroborating signals; zero by default."""
        return 0.0
