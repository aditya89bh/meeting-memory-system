"""Tests for the replay engine (Phase 9)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from meeting_memory.exceptions import ReplayError
from meeting_memory.replay import (
    ReplayEngine,
    ReplayFilter,
    ReplaySession,
    ReplayTimeline,
)
from meeting_memory.storage import (
    MemoryStatus,
    SQLiteMemoryStore,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
)
from ops_helpers import build_db


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return build_db(tmp_path)


def make_clock(values: list[float]) -> Callable[[], float]:
    """Return a deterministic clock that yields ``values`` in order."""
    iterator = iter(values)
    return lambda: next(iterator)


def test_timeline_all(db: Path) -> None:
    timeline = ReplayEngine(db).timeline()
    assert timeline.meeting_count == 6
    assert timeline.memory_count > 0
    start, end = timeline.date_range
    assert start is not None and end is not None and start <= end


def test_timeline_filter_by_project(db: Path) -> None:
    timeline = ReplayEngine(db).timeline(ReplayFilter(project="Atlas"))
    assert timeline.meeting_count == 3
    assert all("Atlas" in (event.meeting.title or "") for event in timeline.events)


def test_timeline_project_matches_memory_text(db: Path) -> None:
    # "PostgreSQL" never appears in a title, only in decision text.
    timeline = ReplayEngine(db).timeline(ReplayFilter(project="PostgreSQL"))
    assert timeline.meeting_count >= 1


def test_timeline_filter_by_person(db: Path) -> None:
    timeline = ReplayEngine(db).timeline(ReplayFilter(person="Priya"))
    assert timeline.meeting_count >= 1
    assert timeline.meeting_count <= 6


def test_timeline_filter_by_date(db: Path) -> None:
    all_events = ReplayEngine(db).timeline()
    target = all_events.events[0].meeting.date
    assert target is not None
    timeline = ReplayEngine(db).timeline(ReplayFilter(date=target))
    assert timeline.meeting_count >= 1
    assert all(event.meeting.date == target for event in timeline.events)


def test_timeline_filter_by_range(db: Path) -> None:
    result = ReplayEngine(db).replay_range("2025-01-06", "2025-01-13")
    assert result.timeline.meeting_count >= 1


def test_timeline_empty_when_nothing_matches(db: Path) -> None:
    timeline = ReplayEngine(db).timeline(ReplayFilter(date="1999-01-01"))
    assert timeline.meeting_count == 0
    assert timeline.memory_count == 0
    assert timeline.date_range == (None, None)


def test_convenience_replays(db: Path) -> None:
    engine = ReplayEngine(db)
    assert engine.replay_all().steps_played == 6
    assert engine.replay_project("Atlas").timeline.meeting_count == 3
    assert engine.replay_person("Priya").timeline.meeting_count >= 1
    first_date = engine.timeline().events[0].meeting.date
    assert first_date is not None
    assert engine.replay_date(first_date).timeline.meeting_count >= 1


def test_event_and_filter_serialisation(db: Path) -> None:
    timeline = ReplayEngine(db).timeline(ReplayFilter(project="Atlas"))
    event = timeline.events[0]
    assert event.date == event.meeting.date
    payload = event.to_dict()
    assert payload["index"] == 0
    assert "cumulative_by_type" in payload
    timeline_payload = timeline.to_dict()
    assert timeline_payload["meeting_count"] == 3
    assert timeline.filter.describe().startswith("project=")


def test_filter_describe_all() -> None:
    assert ReplayFilter().describe() == "all meetings"
    described = ReplayFilter(
        project="A", person="B", date="d", date_from="f", date_to="t"
    ).describe()
    assert "person=B" in described and "to=t" in described


def test_result_serialisation(db: Path) -> None:
    result = ReplayEngine(db).replay_all()
    payload = result.to_dict()
    assert payload["steps_played"] == 6
    assert payload["memories_played"] == result.memories_played
    assert payload["final_by_type"]


def test_session_step_controls(db: Path) -> None:
    timeline = ReplayEngine(db).timeline()
    session = ReplaySession(timeline)
    assert session.current is None
    assert session.remaining == 6
    first = session.step()
    assert session.position == 1
    assert session.current is first
    assert session.has_next()

    session.seek(6)
    assert not session.has_next()
    with pytest.raises(ReplayError):
        session.step()

    session.reset()
    assert session.position == 0
    with pytest.raises(ReplayError):
        session.seek(99)


def test_session_speed_validation(db: Path) -> None:
    timeline = ReplayEngine(db).timeline()
    with pytest.raises(ReplayError):
        ReplaySession(timeline, speed=0)
    with pytest.raises(ReplayError):
        ReplaySession(timeline, step_delay=-1)


def test_session_step_delay_accumulates_elapsed(db: Path) -> None:
    timeline = ReplayEngine(db).timeline()
    # clock returns pairs around each sleeping step.
    clock = make_clock([0.0, 1.0])
    recorded: list[float] = []
    session = ReplaySession(
        timeline,
        speed=2.0,
        step_delay=0.4,
        sleeper=recorded.append,
        clock=clock,
    )
    session.step()
    assert recorded == [0.2]
    assert session.elapsed_seconds == pytest.approx(1.0)


def test_run_on_empty_timeline() -> None:
    timeline = ReplayTimeline(events=(), filter=ReplayFilter())
    result = ReplaySession(timeline).run()
    assert result.steps_played == 0
    assert result.memories_played == 0
    assert result.final_by_type == {}


def test_matches_handles_missing_date(tmp_path: Path) -> None:
    db = tmp_path / "nodate.db"
    with SQLiteMemoryStore(db) as store:
        store.save_meeting(
            StoredMeeting(
                meeting_id="m-nodate",
                transcript_hash="hash-nodate",
                created_at="2025-01-01T00:00:00+00:00",
                title="Undated Project Atlas Sync",
                date=None,
                participants=("Priya",),
            )
        )
        store.save(
            StoredMemory(
                memory_id="mem-1",
                meeting_id="m-nodate",
                memory_type="fact",
                text="Project Atlas update.",
                confidence=0.9,
                utterance_index=0,
                content_hash="ch-1",
                created_at="2025-01-01T00:00:00+00:00",
                updated_at="2025-01-01T00:00:00+00:00",
                status=MemoryStatus.ACTIVE,
                speaker="Priya",
                evidence=(StoredEvidence(0, 0, 5, "Atlas"),),
            )
        )
    # A date-range filter excludes the undated meeting.
    assert ReplayEngine(db).timeline(ReplayFilter(date_from="2025-01-01")).meeting_count == 0
    assert ReplayEngine(db).timeline(ReplayFilter(date_to="2025-12-31")).meeting_count == 0
    # With no date filter it is included.
    assert ReplayEngine(db).timeline().meeting_count == 1
