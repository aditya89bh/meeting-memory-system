"""Unit tests for the extraction domain models."""

from __future__ import annotations

from datetime import datetime, timezone

from meeting_memory.extraction.models import (
    CommitmentMemory,
    DecisionMemory,
    EvidenceSpan,
    ExtractionResult,
    FactMemory,
    MemoryType,
    QuestionMemory,
)

_AT = datetime(2026, 1, 15, 9, 0, 0, tzinfo=timezone.utc)


def _evidence(index: int = 0, text: str = "we decided") -> EvidenceSpan:
    return EvidenceSpan(utterance_index=index, start=0, end=len(text), text=text)


def _decision(memory_id: str = "m:decision:0", confidence: float = 0.95) -> DecisionMemory:
    return DecisionMemory(
        memory_id=memory_id,
        text="We decided to use Postgres.",
        meeting_id="m",
        utterance_index=0,
        evidence=_evidence(),
        confidence=confidence,
        speaker="Alice",
        extracted_at=_AT,
    )


class TestMemoryType:
    def test_str_returns_value(self) -> None:
        assert str(MemoryType.DECISION) == "decision"
        assert MemoryType.OPEN_LOOP.value == "open_loop"

    def test_all_types_present(self) -> None:
        assert {t.value for t in MemoryType} == {
            "decision",
            "commitment",
            "open_loop",
            "risk",
            "assumption",
            "question",
            "fact",
        }


class TestEvidenceSpan:
    def test_to_dict(self) -> None:
        span = EvidenceSpan(2, 3, 8, "loved")
        assert span.to_dict() == {
            "utterance_index": 2,
            "start": 3,
            "end": 8,
            "text": "loved",
        }


class TestExtractedMemory:
    def test_memory_type_class_var(self) -> None:
        assert _decision().memory_type is MemoryType.DECISION
        assert FactMemory.memory_type is MemoryType.FACT

    def test_to_dict_contains_all_fields(self) -> None:
        data = _decision().to_dict()
        assert data["memory_id"] == "m:decision:0"
        assert data["memory_type"] == "decision"
        assert data["text"] == "We decided to use Postgres."
        assert data["speaker"] == "Alice"
        assert data["meeting_id"] == "m"
        assert data["utterance_index"] == 0
        assert data["confidence"] == 0.95
        assert data["extracted_at"] == "2026-01-15T09:00:00+00:00"
        assert data["evidence"]["text"] == "we decided"
        assert data["metadata"] == {}

    def test_extracted_at_none_serialises_to_none(self) -> None:
        memory = DecisionMemory(
            memory_id="m:decision:1",
            text="x",
            meeting_id="m",
            utterance_index=0,
            evidence=_evidence(),
            confidence=0.5,
        )
        assert memory.to_dict()["extracted_at"] is None
        assert memory.speaker is None

    def test_metadata_preserved(self) -> None:
        memory = QuestionMemory(
            memory_id="m:question:0",
            text="Can we ship?",
            meeting_id="m",
            utterance_index=0,
            evidence=_evidence(text="?"),
            confidence=0.95,
            metadata={"trigger": "?"},
        )
        assert memory.to_dict()["metadata"] == {"trigger": "?"}


class TestCommitmentMemory:
    def test_owner_and_due_in_dict(self) -> None:
        memory = CommitmentMemory(
            memory_id="m:commitment:0",
            text="I will send it by Friday.",
            meeting_id="m",
            utterance_index=1,
            evidence=_evidence(1, "I will"),
            confidence=0.95,
            speaker="Bob",
            owner="Bob",
            due="by Friday",
        )
        data = memory.to_dict()
        assert data["owner"] == "Bob"
        assert data["due"] == "by Friday"

    def test_owner_and_due_default_none(self) -> None:
        memory = CommitmentMemory(
            memory_id="m:commitment:1",
            text="we will handle it",
            meeting_id="m",
            utterance_index=2,
            evidence=_evidence(2, "we will"),
            confidence=0.6,
        )
        data = memory.to_dict()
        assert data["owner"] is None
        assert data["due"] is None


class TestExtractionResult:
    def _result(self) -> ExtractionResult:
        decision = _decision()
        fact = FactMemory(
            memory_id="m:fact:3",
            text="We have 1000 users.",
            meeting_id="m",
            utterance_index=3,
            evidence=_evidence(3, "users"),
            confidence=0.75,
        )
        question = QuestionMemory(
            memory_id="m:question:2",
            text="Should we ship?",
            meeting_id="m",
            utterance_index=2,
            evidence=_evidence(2, "?"),
            confidence=0.95,
        )
        return ExtractionResult(
            meeting_id="m",
            memories=(decision, question, fact),
            meeting_metadata={"title": "Sync"},
            warnings=("dropped one",),
        )

    def test_total(self) -> None:
        assert self._result().total == 3

    def test_counts_ordered_and_nonzero_only(self) -> None:
        counts = self._result().counts()
        assert counts == {"decision": 1, "question": 1, "fact": 1}
        assert list(counts) == ["decision", "question", "fact"]

    def test_grouped_orders_by_canonical_type_order(self) -> None:
        groups = self._result().grouped()
        assert list(groups) == ["decision", "question", "fact"]
        assert groups["decision"][0].memory_type is MemoryType.DECISION

    def test_to_dict_structure(self) -> None:
        data = self._result().to_dict()
        assert data["meeting_id"] == "m"
        assert data["meeting"] == {"title": "Sync"}
        assert data["total"] == 3
        assert data["counts"] == {"decision": 1, "question": 1, "fact": 1}
        assert set(data["memories"]) == {"decision", "question", "fact"}
        assert data["warnings"] == ["dropped one"]

    def test_empty_result(self) -> None:
        result = ExtractionResult(meeting_id="m")
        assert result.total == 0
        assert result.counts() == {}
        assert result.grouped() == {}
        assert result.to_dict()["memories"] == {}
