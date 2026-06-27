"""Unit tests for the deterministic ranking model and explanation builder."""

from __future__ import annotations

from meeting_memory.retrieval import (
    RankedMemory,
    RankingWeights,
    RetrievalExplanation,
    RetrievalFilter,
    explain_match,
    score_components,
    score_memory,
)
from meeting_memory.retrieval.ranking import (
    meeting_score,
    phrase_score,
    status_score,
    text_score,
)
from meeting_memory.storage import MemoryStatus, StoredMeeting, StoredMemory


def _memory(
    *,
    memory_id: str = "m:decision:0",
    memory_type: str = "decision",
    text: str = "We decided to adopt postgres for the platform.",
    confidence: float = 0.9,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    speaker: str | None = "Alice",
    metadata: dict[str, str] | None = None,
) -> StoredMemory:
    return StoredMemory(
        memory_id=memory_id,
        meeting_id="m",
        memory_type=memory_type,
        text=text,
        confidence=confidence,
        utterance_index=1,
        content_hash="hash",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        status=status,
        speaker=speaker,
        metadata=metadata or {},
    )


def _meeting(date: str = "2026-01-05") -> StoredMeeting:
    return StoredMeeting(
        meeting_id="m",
        transcript_hash="th",
        created_at="2026-01-01T00:00:00+00:00",
        title="Platform Sync",
        date=date,
        participants=("Alice", "Bob"),
    )


def test_status_score_orders_lifecycle() -> None:
    assert status_score(MemoryStatus.ACTIVE) == 1.0
    assert status_score(MemoryStatus.RESOLVED) < status_score(MemoryStatus.ACTIVE)
    assert status_score(MemoryStatus.DELETED) < status_score(MemoryStatus.ARCHIVED)


def test_text_score_is_term_coverage() -> None:
    memory = _memory()
    assert text_score(memory, ()) == 1.0
    assert text_score(memory, ("postgres",)) == 1.0
    assert text_score(memory, ("postgres", "missing")) == 0.5
    assert text_score(memory, ("missing",)) == 0.0


def test_meeting_score_uses_title_and_participants() -> None:
    meeting = _meeting()
    assert meeting_score(meeting, ()) == 1.0
    assert meeting_score(meeting, ("platform",)) == 1.0
    assert meeting_score(None, ("platform",)) == 0.0


def test_phrase_score_requires_exact_contiguous_match() -> None:
    memory = _memory(text="we adopt postgres now")
    assert phrase_score(memory, None) == 1.0
    assert phrase_score(memory, "adopt postgres") == 1.0
    assert phrase_score(memory, "postgres adopt") == 0.0


def test_score_is_bounded_and_deterministic() -> None:
    memory = _memory()
    meeting = _meeting()
    applied = RetrievalFilter(terms=("postgres",), memory_types=frozenset({"decision"}))
    first = score_memory(memory, meeting, applied, recency=1.0)
    second = score_memory(memory, meeting, applied, recency=1.0)
    assert first == second
    assert 0.0 <= first <= 1.0


def test_active_outranks_archived_all_else_equal() -> None:
    applied = RetrievalFilter(terms=("postgres",))
    active = score_memory(_memory(status=MemoryStatus.ACTIVE), _meeting(), applied, recency=1.0)
    archived = score_memory(_memory(status=MemoryStatus.ARCHIVED), _meeting(), applied, recency=1.0)
    assert active > archived


def test_recency_increases_score() -> None:
    applied = RetrievalFilter(terms=("postgres",))
    older = score_memory(_memory(), _meeting(), applied, recency=0.0)
    newer = score_memory(_memory(), _meeting(), applied, recency=1.0)
    assert newer > older


def test_weights_are_configurable() -> None:
    applied = RetrievalFilter(terms=("postgres",))
    memory = _memory(confidence=0.1)
    high_conf = RankingWeights(
        text=0.0, phrase=0.0, confidence=1.0, recency=0.0, status=0.0, meeting=0.0
    )
    assert score_memory(memory, _meeting(), applied, recency=1.0, weights=high_conf) == 0.1


def test_explanation_lists_concrete_reasons() -> None:
    memory = _memory()
    meeting = _meeting()
    applied = RetrievalFilter(
        terms=("postgres",),
        memory_types=frozenset({"decision"}),
        speakers=frozenset({"Alice"}),
        statuses=frozenset({MemoryStatus.ACTIVE}),
        min_confidence=0.8,
    )
    components = score_components(memory, meeting, applied, recency=1.0)
    explanation = explain_match(memory, meeting, applied, components, RankingWeights())
    details = [reason.detail for reason in explanation.reasons]
    assert "speaker Alice" in details
    assert "memory type decision" in details
    assert 'keyword "postgres"' in details
    assert "status active" in details
    assert any(detail.startswith("confidence \u2265") for detail in details)


def test_explanation_falls_back_to_confidence() -> None:
    memory = _memory()
    applied = RetrievalFilter()
    components = score_components(memory, None, applied, recency=1.0)
    explanation = explain_match(memory, None, applied, components, RankingWeights())
    assert len(explanation.reasons) == 1
    assert explanation.reasons[0].factor == "confidence"


def test_explanation_reports_date_and_month() -> None:
    memory = _memory()
    meeting = _meeting(date="2026-03-15")
    applied = RetrievalFilter(date_from="2026-01-01", date_to="2026-12-31", months=frozenset({3}))
    components = score_components(memory, meeting, applied, recency=0.5)
    explanation = explain_match(memory, meeting, applied, components, RankingWeights())
    details = [reason.detail for reason in explanation.reasons]
    assert any("within date range" in detail for detail in details)
    assert "meeting month 03" in details


def test_explanation_reports_meeting_and_participant() -> None:
    memory = _memory()
    meeting = _meeting()
    applied = RetrievalFilter(meeting_ids=frozenset({"m"}), participants=frozenset({"Bob"}))
    components = score_components(memory, meeting, applied, recency=1.0)
    explanation = explain_match(memory, meeting, applied, components, RankingWeights())
    details = [reason.detail for reason in explanation.reasons]
    assert "meeting m" in details
    assert "participant Bob" in details


def test_explanation_ignores_non_matching_filter_values() -> None:
    memory = _memory(text="we adopt postgres now")
    meeting = _meeting(date="2026-03-15")
    applied = RetrievalFilter(
        terms=("adopt", "postgres", "absent"),
        memory_types=frozenset({"decision", "risk"}),
        speakers=frozenset({"Alice", "Zoe"}),
        statuses=frozenset({MemoryStatus.ACTIVE, MemoryStatus.ARCHIVED}),
        participants=frozenset({"Bob", "Zoe"}),
        months=frozenset({4}),
    )
    components = score_components(memory, meeting, applied, recency=1.0)
    explanation = explain_match(memory, meeting, applied, components, RankingWeights())
    details = [reason.detail for reason in explanation.reasons]
    assert "speaker Alice" in details and "speaker Zoe" not in details
    assert "memory type decision" in details and "memory type risk" not in details
    assert 'keyword "absent"' not in details
    assert "participant Bob" in details and "participant Zoe" not in details
    assert not any("meeting month" in detail for detail in details)


def test_explanation_includes_exact_phrase() -> None:
    memory = _memory(text="we adopt postgres now")
    applied = RetrievalFilter(terms=("adopt", "postgres"))
    components = score_components(memory, None, applied, recency=1.0)
    explanation = explain_match(memory, None, applied, components, RankingWeights())
    details = [reason.detail for reason in explanation.reasons]
    assert 'exact phrase "adopt postgres"' in details


def test_ranked_memory_to_dict_omits_optional_fields() -> None:
    bare = RankedMemory(memory=_memory(), score=0.5)
    payload = bare.to_dict()
    assert payload["score"] == 0.5
    assert "explanation" not in payload
    assert "context" not in payload
    assert "meeting" not in payload


def test_ranked_memory_to_dict_includes_optional_fields() -> None:
    ranked = RankedMemory(
        memory=_memory(),
        score=0.5,
        explanation=RetrievalExplanation(),
        meeting=_meeting(),
    )
    payload = ranked.to_dict()
    assert "explanation" in payload
    assert payload["meeting"]["meeting_id"] == "m"
