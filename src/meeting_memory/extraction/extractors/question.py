"""Extractor for explicit questions raised during a meeting."""

from __future__ import annotations

from typing import ClassVar

from ...models import Utterance
from ..confidence import HIGH, MEDIUM, MEDIUM_HIGH, VERY_HIGH, score
from ..models import EvidenceSpan, ExtractedMemory, MemoryType, QuestionMemory
from .base import ExtractionContext, PhraseExtractor, PhraseRule, make_memory_id, make_phrase_rule


class QuestionExtractor(PhraseExtractor):
    """Detect questions, prioritising utterances that end with a question mark."""

    memory_type: ClassVar[MemoryType] = MemoryType.QUESTION
    memory_class: ClassVar[type[ExtractedMemory]] = QuestionMemory
    rules: ClassVar[tuple[PhraseRule, ...]] = (
        make_phrase_rule(r"\bquestion is\b", HIGH),
        make_phrase_rule(r"\bcan we\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bshould we\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bdo we\b", MEDIUM),
        make_phrase_rule(r"\bwhat about\b", MEDIUM),
    )

    def extract(self, utterance: Utterance, context: ExtractionContext) -> list[ExtractedMemory]:
        if utterance.text.rstrip().endswith("?"):
            return [self._question_from_mark(utterance, context)]
        return super().extract(utterance, context)

    def _question_from_mark(
        self, utterance: Utterance, context: ExtractionContext
    ) -> ExtractedMemory:
        """Build a high-confidence question for a "?"-terminated utterance."""
        text = utterance.text
        evidence = EvidenceSpan(utterance.index, 0, len(text), text)
        return QuestionMemory(
            memory_id=make_memory_id(context.meeting_id, self.memory_type, utterance.index),
            text=text,
            meeting_id=context.meeting_id,
            utterance_index=utterance.index,
            evidence=evidence,
            confidence=score(VERY_HIGH),
            speaker=utterance.speaker.name or None,
            extracted_at=context.extracted_at,
            metadata={"trigger": "?"},
        )
