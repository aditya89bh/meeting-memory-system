"""Unit tests for the deterministic query planner."""

from __future__ import annotations

from meeting_memory.retrieval import PlannerVocabulary, QueryPlanner, RetrievalQuery
from meeting_memory.storage import MemoryStatus


def _plan(text: str, vocab: PlannerVocabulary | None = None):
    return QueryPlanner().plan(RetrievalQuery(text=text), vocab)


def test_plan_recognises_memory_types() -> None:
    plan = _plan("show every decision and the risks")
    assert plan.memory_types == frozenset({"decision", "risk"})
    assert plan.terms == ()


def test_plan_recognises_open_loop_bigram() -> None:
    plan = _plan("open loops that are pending")
    assert plan.memory_types == frozenset({"open_loop"})
    assert plan.terms == ("pending",)


def test_plan_recognises_status_and_month() -> None:
    plan = _plan("risks in march that are resolved")
    assert plan.memory_types == frozenset({"risk"})
    assert plan.months == frozenset({3})
    assert MemoryStatus.RESOLVED in plan.statuses


def test_plan_resolves_known_speaker_and_participant() -> None:
    vocab = PlannerVocabulary(
        speakers=frozenset({"Alice"}), participants=frozenset({"Alice", "Carol"})
    )
    plan = _plan("alice decisions with carol", vocab)
    assert plan.memory_types == frozenset({"decision"})
    assert plan.speakers == frozenset({"Alice"})
    assert plan.participants == frozenset({"Carol"})
    assert plan.terms == ()


def test_plan_drops_stopwords_and_keeps_keywords() -> None:
    plan = _plan("Show every decision about Project X")
    assert plan.memory_types == frozenset({"decision"})
    assert plan.terms == ("project", "x")
    assert plan.phrase == "Show every decision about Project X"
    assert plan.phrase_core == "project x"


def test_plan_single_keyword_has_no_phrase_core() -> None:
    plan = _plan("postgresql")
    assert plan.terms == ("postgresql",)
    assert plan.phrase_core is None


def test_plan_merges_explicit_query_fields() -> None:
    query = RetrievalQuery(
        text="risks",
        speakers=frozenset({"Bob"}),
        memory_types=frozenset({"commitment"}),
        min_confidence=0.5,
        limit=5,
        offset=2,
    )
    plan = QueryPlanner().plan(query)
    assert plan.memory_types == frozenset({"risk", "commitment"})
    assert plan.speakers == frozenset({"Bob"})
    assert plan.min_confidence == 0.5
    assert plan.limit == 5
    assert plan.offset == 2


def test_plan_without_text_is_structural_only() -> None:
    plan = QueryPlanner().plan(RetrievalQuery(memory_types=frozenset({"fact"})))
    assert plan.terms == ()
    assert plan.phrase is None
    assert plan.memory_types == frozenset({"fact"})


def test_to_storage_query_maps_structured_fields() -> None:
    plan = _plan("alice decisions", PlannerVocabulary(speakers=frozenset({"Alice"})))
    storage_query = plan.to_storage_query()
    assert storage_query.memory_types == frozenset({"decision"})
    assert storage_query.speakers == frozenset({"Alice"})
    assert storage_query.statuses is None


def test_vocabulary_lookups_are_case_insensitive() -> None:
    vocab = PlannerVocabulary(speakers=frozenset({"Alice"}))
    assert vocab.speaker_lookup() == {"alice": "Alice"}
    plan = _plan("ALICE", vocab)
    assert plan.speakers == frozenset({"Alice"})
