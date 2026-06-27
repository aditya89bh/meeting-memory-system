"""Unit tests for extraction validation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from meeting_memory.exceptions import ExtractionValidationError
from meeting_memory.extraction.models import DecisionMemory, EvidenceSpan, MemoryType
from meeting_memory.extraction.validation import (
    check_memory,
    partition_valid,
    validate_memory,
)


def _memory(
    *,
    memory_id: str = "m:decision:0",
    text: str = "We decided.",
    meeting_id: str = "m",
    utterance_index: int = 0,
    confidence: float = 0.9,
    evidence_index: int = 0,
) -> DecisionMemory:
    return DecisionMemory(
        memory_id=memory_id,
        text=text,
        meeting_id=meeting_id,
        utterance_index=utterance_index,
        evidence=EvidenceSpan(evidence_index, 0, 3, "We "),
        confidence=confidence,
    )


def test_valid_memory_returns_none() -> None:
    assert check_memory(_memory(), utterance_count=1) is None


def test_missing_id() -> None:
    assert check_memory(_memory(memory_id=""), utterance_count=1) == "memory is missing an id"


def test_confidence_out_of_range() -> None:
    problem = check_memory(_memory(confidence=1.5), utterance_count=1)
    assert problem is not None and "out of range" in problem


def test_missing_meeting_id() -> None:
    problem = check_memory(_memory(meeting_id=""), utterance_count=1)
    assert problem is not None and "meeting_id" in problem


def test_empty_text() -> None:
    problem = check_memory(_memory(text="   "), utterance_count=1)
    assert problem is not None and "text is empty" in problem


def test_utterance_index_out_of_range() -> None:
    problem = check_memory(_memory(utterance_index=5), utterance_count=2)
    assert problem is not None and "utterance_index" in problem


def test_evidence_index_out_of_range() -> None:
    problem = check_memory(_memory(evidence_index=9), utterance_count=2)
    assert problem is not None and "evidence references utterance 9" in problem


def test_invalid_memory_type() -> None:
    fake = SimpleNamespace(
        memory_id="x",
        memory_type="decision",  # a string, not a MemoryType
        confidence=0.9,
        meeting_id="m",
        text="hi",
        utterance_index=0,
        evidence=SimpleNamespace(utterance_index=0),
    )
    problem = check_memory(fake, utterance_count=1)  # type: ignore[arg-type]
    assert problem is not None and "invalid memory_type" in problem


def test_validate_memory_raises() -> None:
    with pytest.raises(ExtractionValidationError):
        validate_memory(_memory(confidence=2.0), utterance_count=1)


def test_validate_memory_passes() -> None:
    validate_memory(_memory(), utterance_count=1)


def test_partition_valid_splits_and_warns() -> None:
    good = _memory(memory_id="m:decision:0", utterance_index=0)
    bad = _memory(memory_id="m:decision:1", utterance_index=9)
    valid, warnings = partition_valid([good, bad], utterance_count=1)
    assert valid == [good]
    assert len(warnings) == 1
    assert "dropped invalid memory" in warnings[0]


def test_memory_type_enum_is_valid() -> None:
    assert isinstance(_memory().memory_type, MemoryType)
