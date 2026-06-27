"""Unit tests for temporal retrieval: before/after/between/latest/oldest/timeline."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from meeting_memory.retrieval import MemoryRetriever, RetrievalQuery
from meeting_memory.storage import SQLiteMemoryStore, import_meeting

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
        ("mar", "2026-03-15", "postgres"),
    ]:
        path = tmp_path / f"{name}.txt"
        path.write_text(_transcript(name, date, topic), encoding="utf-8")
        import_meeting(path, store, now=_NOW)
    return store


def _meeting_order(result) -> list[str]:
    return [ranked.memory.meeting_id for ranked in result.ranked]


def test_timeline_is_chronological(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).timeline(RetrievalQuery(memory_types=frozenset({"risk"})))
    assert _meeting_order(result) == ["jan", "feb", "mar"]
    store.close()


def test_before_filters_and_orders(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).before(
        "2026-02-28", RetrievalQuery(memory_types=frozenset({"decision"}))
    )
    assert _meeting_order(result) == ["jan", "feb"]
    store.close()


def test_after_filters_and_orders(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).after(
        "2026-02-01", RetrievalQuery(memory_types=frozenset({"decision"}))
    )
    assert _meeting_order(result) == ["feb", "mar"]
    store.close()


def test_between_is_inclusive(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).between(
        "2026-02-10", "2026-03-15", RetrievalQuery(memory_types=frozenset({"risk"}))
    )
    assert _meeting_order(result) == ["feb", "mar"]
    store.close()


def test_latest_returns_most_recent_first(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).latest(2, RetrievalQuery(memory_types=frozenset({"decision"})))
    assert _meeting_order(result) == ["mar", "feb"]
    assert result.stats.candidates == 3
    assert result.stats.returned == 2
    store.close()


def test_oldest_returns_earliest_first(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).oldest(2, RetrievalQuery(memory_types=frozenset({"decision"})))
    assert _meeting_order(result) == ["jan", "feb"]
    store.close()


def test_timeline_context_is_attached(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    result = MemoryRetriever(store).timeline(
        RetrievalQuery(memory_types=frozenset({"commitment"}), context_size=1)
    )
    assert all(ranked.context is not None for ranked in result.ranked)
    store.close()


def test_temporal_methods_without_base_query(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    retriever = MemoryRetriever(store)
    assert retriever.timeline().stats.candidates == 9
    assert retriever.before("2026-01-31").stats.candidates == 3
    assert retriever.after("2026-03-01").stats.candidates == 3
    assert retriever.between("2026-01-01", "2026-02-28").stats.candidates == 6
    assert retriever.latest(2).stats.returned == 2
    assert retriever.oldest(2).stats.returned == 2
    store.close()
