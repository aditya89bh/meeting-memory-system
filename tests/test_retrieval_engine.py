"""Unit tests for the retrieval engine: filters, AND semantics, pagination, context."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from meeting_memory.retrieval import ContextAssembler, MemoryRetriever, RetrievalQuery
from meeting_memory.retrieval.engine import (
    _matches_months,
    _matches_participants,
    _meeting_date,
    _recency_map,
    _searchable,
)
from meeting_memory.retrieval.models import RankedMemory
from meeting_memory.storage import (
    MemoryStatus,
    SQLiteMemoryStore,
    StoredMeeting,
    StoredMemory,
    import_meeting,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _transcript(title: str, date: str, topic: str) -> str:
    return (
        f"---\ntitle: {title}\ndate: {date}\n---\n"
        f"[00:00:05] Alice: We decided to adopt {topic} for the platform.\n"
        f"[00:00:20] Bob: I will deploy {topic} by Friday.\n"
        f"[00:00:35] Alice: There is a risk that {topic} will fail under load.\n"
    )


def _build_store(tmp_path: Path) -> SQLiteMemoryStore:
    store = SQLiteMemoryStore(":memory:")
    for name, date, topic in [
        ("jan", "2026-01-05", "postgres"),
        ("feb", "2026-02-10", "postgres"),
        ("mar", "2026-03-15", "redis"),
    ]:
        path = tmp_path / f"{name}.txt"
        path.write_text(_transcript(name, date, topic), encoding="utf-8")
        import_meeting(path, store, now=_NOW)
    return store


def test_keyword_retrieval_matches_topic(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(RetrievalQuery(text="redis"))
    assert {ranked.memory.meeting_id for ranked in result.ranked} == {"mar"}
    store.close()


def test_type_retrieval(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(RetrievalQuery(memory_types=frozenset({"risk"})))
    assert {ranked.memory.memory_type for ranked in result.ranked} == {"risk"}
    assert result.stats.candidates == 3
    store.close()


def test_speaker_retrieval(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(RetrievalQuery(speakers=frozenset({"Bob"})))
    assert all(ranked.memory.speaker == "Bob" for ranked in result.ranked)
    assert result.stats.candidates == 3
    store.close()


def test_meeting_retrieval(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(RetrievalQuery(meeting_ids=frozenset({"jan"})))
    assert {ranked.memory.meeting_id for ranked in result.ranked} == {"jan"}
    store.close()


def test_status_retrieval(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    store.archive("jan:risk:2")
    result = MemoryRetriever(store).retrieve(
        RetrievalQuery(statuses=frozenset({MemoryStatus.ARCHIVED}))
    )
    assert {ranked.memory.memory_id for ranked in result.ranked} == {"jan:risk:2"}
    store.close()


def test_date_retrieval(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(
        RetrievalQuery(date_from="2026-02-01", date_to="2026-02-28")
    )
    assert {ranked.memory.meeting_id for ranked in result.ranked} == {"feb"}
    store.close()


def test_month_filter(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(RetrievalQuery(months=frozenset({3})))
    assert {ranked.memory.meeting_id for ranked in result.ranked} == {"mar"}
    store.close()


def test_combined_filters_use_and_semantics(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(
        RetrievalQuery(text="postgres", memory_types=frozenset({"risk"}))
    )
    assert {ranked.memory.memory_id for ranked in result.ranked} == {
        "jan:risk:2",
        "feb:risk:2",
    }
    store.close()


def test_keyword_and_excludes_partial_matches(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    # "redis" only exists in March; combined with the absent term it returns nothing.
    result = MemoryRetriever(store).retrieve(RetrievalQuery(text="redis postgres"))
    assert result.ranked == ()
    assert result.stats.candidates == 0
    store.close()


def test_pagination_limit_and_offset(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    retriever = MemoryRetriever(store)
    full = retriever.retrieve(RetrievalQuery(memory_types=frozenset({"decision"})))
    page = retriever.retrieve(
        RetrievalQuery(memory_types=frozenset({"decision"}), limit=1, offset=1)
    )
    assert page.stats.candidates == full.stats.candidates == 3
    assert page.stats.returned == 1
    assert page.ranked[0].memory.memory_id == full.ranked[1].memory.memory_id
    store.close()


def test_relevance_orders_by_score_then_recency(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(RetrievalQuery(text="postgres"))
    scores = [ranked.score for ranked in result.ranked]
    assert scores == sorted(scores, reverse=True)
    # Same-score decisions: the more recent meeting (feb) ranks before jan.
    decisions = [r for r in result.ranked if r.memory.memory_type == "decision"]
    assert [d.memory.meeting_id for d in decisions] == ["feb", "jan"]
    store.close()


def test_context_window_is_attached(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(
        RetrievalQuery(memory_types=frozenset({"commitment"}), context_size=1)
    )
    context = result.ranked[0].context
    assert context is not None
    assert context.target is not None
    assert context.target.is_match is True
    assert context.target.text.startswith("I will deploy")
    assert len(context.before) == 1
    assert len(context.after) == 1
    store.close()


def test_context_falls_back_when_source_missing(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(":memory:")
    path = tmp_path / "gone.txt"
    path.write_text(_transcript("gone", "2026-04-01", "kafka"), encoding="utf-8")
    import_meeting(path, store, now=_NOW)
    path.unlink()
    result = MemoryRetriever(store).retrieve(
        RetrievalQuery(memory_types=frozenset({"decision"}), context_size=2)
    )
    context = result.ranked[0].context
    assert context is not None
    assert context.before == ()
    assert context.after == ()
    assert context.target is not None
    assert context.target.text == result.ranked[0].memory.text
    store.close()


def test_empty_store_returns_no_results() -> None:
    store = SQLiteMemoryStore(":memory:")
    result = MemoryRetriever(store).retrieve(RetrievalQuery(text="anything"))
    assert result.ranked == ()
    assert result.stats == result.stats.__class__(0, 0, 0, None)
    store.close()


def test_result_to_dict_round_trips(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).retrieve(RetrievalQuery(text="postgres", limit=1))
    payload = result.to_dict()
    assert payload["stats"]["returned"] == 1
    assert payload["results"][0]["memory"]["memory_id"]
    assert "explanation" in payload["results"][0]
    store.close()


def test_participant_filter(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    matched = MemoryRetriever(store).retrieve(RetrievalQuery(participants=frozenset({"Bob"})))
    assert matched.stats.candidates == 9
    missed = MemoryRetriever(store).retrieve(RetrievalQuery(participants=frozenset({"Zoe"})))
    assert missed.ranked == ()
    store.close()


def _dateless_transcript() -> str:
    return (
        "[00:00:05] Alice: We decided to adopt kafka for the platform.\n"
        "[00:00:20] Bob: I will deploy kafka by Friday.\n"
    )


def test_dateless_meeting_is_handled(tmp_path: Path) -> None:
    store = SQLiteMemoryStore(":memory:")
    path = tmp_path / "nodate.txt"
    path.write_text(_dateless_transcript(), encoding="utf-8")
    import_meeting(path, store, now=_NOW)
    # Month filtering excludes dateless meetings; plain retrieval still works.
    assert MemoryRetriever(store).retrieve(RetrievalQuery(months=frozenset({3}))).ranked == ()
    result = MemoryRetriever(store).retrieve(RetrievalQuery(memory_types=frozenset({"decision"})))
    assert result.stats.candidates == 1
    store.close()


def _memory(meeting_id: str = "m") -> StoredMemory:
    return StoredMemory(
        memory_id=f"{meeting_id}:decision:0",
        meeting_id=meeting_id,
        memory_type="decision",
        text="we adopt postgres",
        confidence=0.9,
        utterance_index=0,
        content_hash="h",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        speaker="Alice",
    )


def _meeting(meeting_id: str = "m", date: str | None = "2026-01-05") -> StoredMeeting:
    return StoredMeeting(
        meeting_id=meeting_id,
        transcript_hash="t",
        created_at="2026-01-01T00:00:00+00:00",
        title="Sync",
        date=date,
        participants=("Alice", "Bob"),
    )


def test_context_assembler_without_source() -> None:
    assembler = ContextAssembler()
    no_meeting = assembler.assemble(_memory(), None, 1)
    assert no_meeting.target is not None
    assert no_meeting.before == ()
    sourceless = assembler.assemble(_memory(), _meeting(), 1)
    assert sourceless.target is not None
    assert sourceless.target.text == "we adopt postgres"


def test_searchable_without_meeting() -> None:
    text = _searchable(_memory(), None)
    assert "postgres" in text
    assert "sync" not in text


def test_matches_participants_without_meeting() -> None:
    assert _matches_participants(None, frozenset({"Bob"})) is False
    assert _matches_participants(_meeting(), frozenset({"Bob"})) is True


def test_matches_months_without_date() -> None:
    assert _matches_months(_meeting(date=None), frozenset({1})) is False
    assert _matches_months(_meeting(date="2026-01-05"), frozenset({1})) is True


def test_meeting_date_helper() -> None:
    assert _meeting_date(RankedMemory(memory=_memory(), score=0.5)) == ""
    item = RankedMemory(memory=_memory(), score=0.5, meeting=_meeting())
    assert _meeting_date(item) == "2026-01-05"


def test_recency_map_variants() -> None:
    single = _recency_map([_memory("a")], {"a": _meeting("a")})
    assert single == {"a": 1.0}
    meetings = {"a": _meeting("a", "2026-01-01"), "b": _meeting("b", "2026-02-01")}
    spread = _recency_map([_memory("a"), _memory("b")], meetings)
    assert spread == {"a": 0.0, "b": 1.0}
    undated = _recency_map(
        [_memory("a"), _memory("b"), _memory("c")],
        {
            "a": _meeting("a", "2026-01-01"),
            "b": _meeting("b", "2026-02-01"),
            "c": _meeting("c", None),
        },
    )
    assert undated["c"] == 0.0
    assert undated["b"] == 1.0
