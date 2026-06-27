"""Unit tests for memory deduplication."""

from __future__ import annotations

from meeting_memory.extraction.dedup import deduplicate, normalize_text
from meeting_memory.extraction.models import (
    DecisionMemory,
    EvidenceSpan,
    ExtractedMemory,
    RiskMemory,
)


def _memory(
    cls: type[ExtractedMemory],
    text: str,
    confidence: float,
    *,
    index: int = 0,
) -> ExtractedMemory:
    return cls(
        memory_id=f"m:{cls.memory_type.value}:{index}",
        text=text,
        meeting_id="m",
        utterance_index=index,
        evidence=EvidenceSpan(index, 0, len(text), text),
        confidence=confidence,
    )


def test_normalize_text_lowercases_and_strips_punctuation() -> None:
    assert normalize_text("We decided!") == "we decided"
    assert normalize_text("  We   decided. ") == "we decided"


def test_deduplicate_keeps_highest_confidence() -> None:
    low = _memory(DecisionMemory, "We decided.", 0.6, index=0)
    high = _memory(DecisionMemory, "we decided", 0.95, index=1)
    result = deduplicate([low, high])
    assert len(result) == 1
    assert result[0].confidence == 0.95


def test_deduplicate_keeps_distinct_types() -> None:
    decision = _memory(DecisionMemory, "same words", 0.9, index=0)
    risk = _memory(RiskMemory, "same words", 0.9, index=1)
    result = deduplicate([decision, risk])
    assert len(result) == 2


def test_deduplicate_preserves_order() -> None:
    first = _memory(DecisionMemory, "alpha", 0.9, index=0)
    second = _memory(RiskMemory, "beta", 0.9, index=1)
    third = _memory(DecisionMemory, "gamma", 0.9, index=2)
    result = deduplicate([first, second, third])
    assert [m.text for m in result] == ["alpha", "beta", "gamma"]


def test_deduplicate_tie_keeps_earliest() -> None:
    first = _memory(DecisionMemory, "we decided", 0.9, index=0)
    second = _memory(DecisionMemory, "We decided!", 0.9, index=1)
    result = deduplicate([first, second])
    assert len(result) == 1
    assert result[0].utterance_index == 0


def test_deduplicate_empty() -> None:
    assert deduplicate([]) == []
