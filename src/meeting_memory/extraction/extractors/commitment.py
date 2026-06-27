"""Extractor for commitments: actions someone agreed to take."""

from __future__ import annotations

import re
from typing import ClassVar

from ...models import Utterance
from ..confidence import HIGH, MEDIUM, MEDIUM_HIGH, OWNER_DEADLINE_BOOST
from ..models import CommitmentMemory, ExtractedMemory, MemoryType
from .base import PhraseExtractor, PhraseRule, _MemoryFields, make_phrase_rule

_WEEKDAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"

# Detects an explicit deadline phrase such as "by Friday" or "before next meeting".
_DUE_RE = re.compile(
    r"\b(?:"
    r"by (?:end of (?:day|week|month)|eod|cob|today|tomorrow|next week|next month|"
    rf"{_WEEKDAYS}|\w+ \d{{1,2}}(?:st|nd|rd|th)?|\d{{1,2}}/\d{{1,2}})"
    r"|before (?:the )?next meeting"
    r")\b",
    re.IGNORECASE,
)

# Detects an explicit assignee such as "assigned to Dana".
_ASSIGNEE_RE = re.compile(r"\bassigned to ([A-Z][\w.'-]*(?: [A-Z][\w.'-]*)?)")

# Detects first-person commitment ("I will", "I'll").
_FIRST_PERSON_RE = re.compile(r"\bI(?:'ll| will)\b")


class CommitmentExtractor(PhraseExtractor):
    """Detect commitment language, capturing an owner and deadline when present."""

    memory_type: ClassVar[MemoryType] = MemoryType.COMMITMENT
    memory_class: ClassVar[type[ExtractedMemory]] = CommitmentMemory
    rules: ClassVar[tuple[PhraseRule, ...]] = (
        make_phrase_rule(r"\bassigned to\b", HIGH),
        make_phrase_rule(r"\bI(?:'ll| will)\b", HIGH),
        make_phrase_rule(r"\bplease take\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bplease (?:handle|own|prepare|send|review|follow up)\b", MEDIUM_HIGH),
        make_phrase_rule(r"\bwe will\b", MEDIUM),
        make_phrase_rule(r"\bcan you\b", MEDIUM),
        make_phrase_rule(r"\bby (?:" + _WEEKDAYS + r")\b", MEDIUM),
        make_phrase_rule(r"\bbefore (?:the )?next meeting\b", MEDIUM),
    )

    def _confidence_boost(self, utterance: Utterance, match: re.Match[str]) -> float:
        if self._detect_owner(utterance) and self._detect_due(utterance.text):
            return OWNER_DEADLINE_BOOST
        return 0.0

    def _construct(
        self,
        fields: _MemoryFields,
        utterance: Utterance,
        match: re.Match[str],
    ) -> ExtractedMemory:
        return CommitmentMemory(
            memory_id=fields.memory_id,
            text=fields.text,
            meeting_id=fields.meeting_id,
            utterance_index=fields.utterance_index,
            evidence=fields.evidence,
            confidence=fields.confidence,
            speaker=fields.speaker,
            extracted_at=fields.extracted_at,
            metadata=fields.metadata,
            owner=self._detect_owner(utterance),
            due=self._detect_due(utterance.text),
        )

    @staticmethod
    def _detect_owner(utterance: Utterance) -> str | None:
        """Identify who owns the commitment, if it can be determined."""
        assignee = _ASSIGNEE_RE.search(utterance.text)
        if assignee is not None:
            return assignee.group(1).strip()
        if _FIRST_PERSON_RE.search(utterance.text):
            return utterance.speaker.name or None
        return None

    @staticmethod
    def _detect_due(text: str) -> str | None:
        """Extract an explicit deadline phrase, if present."""
        found = _DUE_RE.search(text)
        return found.group(0) if found is not None else None
