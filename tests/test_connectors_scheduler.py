"""Tests for deterministic scheduling and the cron-subset parser."""

from __future__ import annotations

from datetime import datetime

import pytest

from meeting_memory.connectors import Schedule, ScheduleFrequency
from meeting_memory.connectors.scheduler import (
    Scheduler,
    cron_next,
    next_run,
    parse_cron,
    simulate,
)
from meeting_memory.exceptions import ScheduleError

# A Saturday afternoon (2026-06-27 is a Saturday).
BASE = datetime(2026, 6, 27, 14, 30)


def test_hourly_daily_weekly() -> None:
    assert next_run(Schedule(ScheduleFrequency.HOURLY), BASE) == datetime(2026, 6, 27, 15, 0)
    assert next_run(Schedule(ScheduleFrequency.DAILY), BASE) == datetime(2026, 6, 28, 0, 0)
    # Next Monday after a Saturday is 2026-06-29.
    assert next_run(Schedule(ScheduleFrequency.WEEKLY), BASE) == datetime(2026, 6, 29, 0, 0)


def test_manual_has_no_runs() -> None:
    assert next_run(Schedule(ScheduleFrequency.MANUAL), BASE) is None


def test_once_variants() -> None:
    assert next_run(Schedule(ScheduleFrequency.ONCE), BASE) == BASE
    future = Schedule(ScheduleFrequency.ONCE, at="2026-06-28T09:00:00")
    assert next_run(future, BASE) == datetime(2026, 6, 28, 9, 0)
    past = Schedule(ScheduleFrequency.ONCE, at="2026-06-01T09:00:00")
    assert next_run(past, BASE) is None


def test_once_invalid_at() -> None:
    with pytest.raises(ScheduleError):
        next_run(Schedule(ScheduleFrequency.ONCE, at="not-a-time"), BASE)


def test_cron_requires_expression() -> None:
    with pytest.raises(ScheduleError):
        next_run(Schedule(ScheduleFrequency.CRON), BASE)


def test_cron_basic_minute_step() -> None:
    assert cron_next("*/15 * * * *", BASE) == datetime(2026, 6, 27, 14, 45)


def test_cron_specific_day_of_week() -> None:
    # Mondays at 09:00 -> next Monday 2026-06-29.
    assert cron_next("0 9 * * 1", BASE) == datetime(2026, 6, 29, 9, 0)


def test_cron_day_of_month_rollover() -> None:
    # First of the month at midnight -> next month.
    assert cron_next("0 0 1 * *", BASE) == datetime(2026, 7, 1, 0, 0)


def test_cron_month_field() -> None:
    # Only January is allowed -> rolls to next year.
    assert cron_next("0 0 1 1 *", BASE) == datetime(2027, 1, 1, 0, 0)


def test_cron_range_and_list() -> None:
    spec = parse_cron("0 9-11,13 * * *")
    assert spec.hour == frozenset({9, 10, 11, 13})


def test_cron_dom_or_dow_semantics() -> None:
    # Both restricted -> OR. Day 1 OR Monday.
    nxt = cron_next("0 0 1 * 1", BASE)
    assert nxt.day == 1 or nxt.weekday() == 0


def test_parse_cron_errors() -> None:
    with pytest.raises(ScheduleError):
        parse_cron("* * * *")  # too few fields
    with pytest.raises(ScheduleError):
        parse_cron("99 * * * *")  # out of range
    with pytest.raises(ScheduleError):
        parse_cron("*/0 * * * *")  # zero step
    with pytest.raises(ScheduleError):
        parse_cron("a * * * *")  # non-numeric
    with pytest.raises(ScheduleError):
        parse_cron("1- * * * *")  # bad range
    with pytest.raises(ScheduleError):
        parse_cron(" * * * *,")  # trailing empty token in a field
    with pytest.raises(ScheduleError):
        parse_cron("*/x * * * *")  # non-numeric step


def test_cron_impossible_spec_raises() -> None:
    with pytest.raises(ScheduleError):
        cron_next("0 0 30 2 *", BASE)  # Feb 30 never occurs


def test_simulate_daily() -> None:
    runs = simulate(Schedule(ScheduleFrequency.DAILY), start=BASE, count=3)
    assert runs == [
        datetime(2026, 6, 28, 0, 0),
        datetime(2026, 6, 29, 0, 0),
        datetime(2026, 6, 30, 0, 0),
    ]


def test_simulate_manual_is_empty() -> None:
    assert simulate(Schedule(ScheduleFrequency.MANUAL), start=BASE, count=5) == []


def test_simulate_once_yields_single() -> None:
    schedule = Schedule(ScheduleFrequency.ONCE, at="2026-06-28T09:00:00")
    runs = simulate(schedule, start=BASE, count=5)
    assert runs == [datetime(2026, 6, 28, 9, 0)]


def test_simulate_negative_count() -> None:
    with pytest.raises(ScheduleError):
        simulate(Schedule(ScheduleFrequency.DAILY), start=BASE, count=-1)


def test_scheduler_object_delegates() -> None:
    scheduler = Scheduler()
    assert scheduler.next_run(Schedule(ScheduleFrequency.HOURLY), BASE) == datetime(
        2026, 6, 27, 15, 0
    )
    assert len(scheduler.simulate(Schedule(ScheduleFrequency.DAILY), start=BASE, count=2)) == 2
