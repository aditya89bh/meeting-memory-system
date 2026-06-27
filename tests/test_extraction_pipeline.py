"""Unit tests for the extraction pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

from meeting_memory.extraction import (
    ExtractionConfig,
    ExtractionPipeline,
    MemoryType,
    derive_meeting_id,
    extract_memories,
)
from meeting_memory.extraction.extractors import DecisionExtractor
from meeting_memory.parser import parse_text

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_SAMPLE = "\n".join(
    [
        "Alice: We decided to use Postgres for storage.",
        "Bob: I will send the migration plan by Friday.",
        "Carol: There is a risk the vendor API might fail under load.",
        "Dana: Assuming traffic stays flat, we are fine.",
        "Erin: Can we ship before the launch?",
        "Frank: This item is pending and to be confirmed.",
        "Grace: Our top customer needs 99.9% uptime.",
    ]
)


def _meeting(text: str = _SAMPLE, **kwargs: str):
    return parse_text(text, **kwargs)


class TestDeriveMeetingId:
    def test_from_source_path(self) -> None:
        meeting = _meeting(source_path="/tmp/team_sync.txt")
        assert derive_meeting_id(meeting) == "team_sync"

    def test_from_title_slug(self) -> None:
        meeting = parse_text("---\ntitle: Q1 Planning!\n---\nAlice: We decided to ship.")
        assert derive_meeting_id(meeting) == "q1-planning"

    def test_fallback(self) -> None:
        assert derive_meeting_id(parse_text("Alice: We decided to ship.")) == "meeting"


class TestPipelineExtraction:
    def test_extracts_all_types(self) -> None:
        result = extract_memories(_meeting(source_path="/tmp/sync.txt"), now=_NOW)
        assert result.meeting_id == "sync"
        assert result.counts() == {
            "decision": 1,
            "commitment": 1,
            "open_loop": 1,
            "risk": 1,
            "assumption": 1,
            "question": 1,
            "fact": 1,
        }
        assert result.total == 7

    def test_memories_sorted_by_utterance_then_type(self) -> None:
        result = extract_memories(_meeting(), now=_NOW)
        indices = [m.utterance_index for m in result.memories]
        assert indices == sorted(indices)

    def test_extracted_at_is_stamped(self) -> None:
        result = extract_memories(_meeting(), now=_NOW)
        assert all(m.extracted_at == _NOW for m in result.memories)

    def test_meeting_metadata_included(self) -> None:
        result = extract_memories(_meeting(source_path="/tmp/sync.txt"), now=_NOW)
        assert result.meeting_metadata["source_path"] == "/tmp/sync.txt"

    def test_warnings_empty_for_normal_meeting(self) -> None:
        assert extract_memories(_meeting(), now=_NOW).warnings == ()


class TestPipelineConfig:
    def test_filter_by_type(self) -> None:
        config = ExtractionConfig(
            enabled_types=frozenset({MemoryType.DECISION, MemoryType.COMMITMENT})
        )
        result = extract_memories(_meeting(), config=config, now=_NOW)
        assert set(result.counts()) == {"decision", "commitment"}

    def test_disable_all_types(self) -> None:
        config = ExtractionConfig(enabled_types=frozenset())
        assert extract_memories(_meeting(), config=config, now=_NOW).total == 0

    def test_min_confidence_filter(self) -> None:
        config = ExtractionConfig(min_confidence=0.9)
        result = extract_memories(_meeting(), config=config, now=_NOW)
        assert all(m.confidence >= 0.9 for m in result.memories)
        # decision, commitment (boosted), and question all score >= 0.9 here.
        assert set(result.counts()) == {"decision", "commitment", "question"}

    def test_deduplicate_on_by_default(self) -> None:
        meeting = parse_text("Alice: We decided to ship.\nBob: We decided to ship.")
        result = extract_memories(meeting, now=_NOW)
        assert result.counts().get("decision") == 1

    def test_no_deduplicate_keeps_repeats(self) -> None:
        meeting = parse_text("Alice: We decided to ship.\nBob: We decided to ship.")
        config = ExtractionConfig(deduplicate=False)
        result = extract_memories(meeting, config=config, now=_NOW)
        assert result.counts().get("decision") == 2


class TestPipelineEdgeCases:
    def test_no_memory_meeting(self) -> None:
        meeting = parse_text("Alice: Good morning everyone.\nBob: Hello there.")
        result = extract_memories(meeting, now=_NOW)
        assert result.total == 0
        assert result.counts() == {}
        assert result.warnings == ()

    def test_empty_meeting(self) -> None:
        result = extract_memories(parse_text(""), meeting_id="empty", now=_NOW)
        assert result.total == 0
        assert result.meeting_id == "empty"

    def test_custom_extractor_registry(self) -> None:
        pipeline = ExtractionPipeline([DecisionExtractor()])
        result = pipeline.extract(_meeting(), now=_NOW)
        assert set(result.counts()) == {"decision"}

    def test_explicit_meeting_id_overrides_derivation(self) -> None:
        meeting = _meeting(source_path="/tmp/sync.txt")
        result = extract_memories(meeting, meeting_id="custom", now=_NOW)
        assert result.meeting_id == "custom"
        assert all(m.meeting_id == "custom" for m in result.memories)
