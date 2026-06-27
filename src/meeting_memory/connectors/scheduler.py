"""Deterministic scheduling primitives (Phase 7).

The scheduler computes *when* an automation job would next run; it never sleeps,
forks, or starts a background daemon. Frequencies cover run-once, hourly, daily,
weekly, manual, and a cron-like subset. A simulation mode lists the next N run
times from a fixed start, which makes schedules fully testable.

The cron subset supports the five standard fields (minute, hour, day-of-month,
month, day-of-week) with ``*``, integers, ranges (``a-b``), steps (``*/n`` and
``a-b/n``), and comma-separated lists. Day-of-week uses ``0=Sunday`` .. ``6=Saturday``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..exceptions import ScheduleError
from .models import Schedule, ScheduleFrequency

# Upper bound on the per-call minute search for cron (impossible specs raise).
_MAX_CRON_ITERATIONS = 1_000_000

_FIELD_BOUNDS: tuple[tuple[int, int], ...] = (
    (0, 59),  # minute
    (0, 23),  # hour
    (1, 31),  # day of month
    (1, 12),  # month
    (0, 6),  # day of week (0 = Sunday)
)


def _parse_token(token: str, low: int, high: int) -> set[int]:
    """Parse one cron token (``*``, ``a``, ``a-b``, ``*/n``, ``a-b/n``)."""
    step = 1
    base = token
    if "/" in token:
        base, _, raw_step = token.partition("/")
        try:
            step = int(raw_step)
        except ValueError as exc:
            raise ScheduleError(f"invalid cron step in {token!r}") from exc
        if step <= 0:
            raise ScheduleError(f"cron step must be positive in {token!r}")

    if base == "*":
        start, end = low, high
    elif "-" in base:
        start_raw, _, end_raw = base.partition("-")
        try:
            start, end = int(start_raw), int(end_raw)
        except ValueError as exc:
            raise ScheduleError(f"invalid cron range in {token!r}") from exc
    else:
        try:
            start = end = int(base)
        except ValueError as exc:
            raise ScheduleError(f"invalid cron value in {token!r}") from exc

    if start < low or end > high or start > end:
        raise ScheduleError(f"cron value out of range [{low}-{high}] in {token!r}")
    return set(range(start, end + 1, step))


def _parse_field(field: str, low: int, high: int) -> tuple[frozenset[int], bool]:
    """Parse one cron field into its value set and a wildcard flag."""
    field = field.strip()
    if not field:
        raise ScheduleError("empty cron field")
    is_wildcard = field == "*"
    values: set[int] = set()
    for token in field.split(","):
        token = token.strip()
        if not token:
            raise ScheduleError("empty cron token")
        values |= _parse_token(token, low, high)
    return frozenset(values), is_wildcard


@dataclass(frozen=True)
class CronSpec:
    """A parsed cron expression with per-field value sets and wildcard flags."""

    minute: frozenset[int]
    hour: frozenset[int]
    day_of_month: frozenset[int]
    month: frozenset[int]
    day_of_week: frozenset[int]
    dom_wildcard: bool
    dow_wildcard: bool

    def day_matches(self, moment: datetime) -> bool:
        """Apply the standard cron day-of-month / day-of-week OR semantics."""
        cron_dow = (moment.weekday() + 1) % 7  # Monday=0 -> Sunday=0
        if not self.dom_wildcard and not self.dow_wildcard:
            return moment.day in self.day_of_month or cron_dow in self.day_of_week
        if not self.dom_wildcard:
            return moment.day in self.day_of_month
        if not self.dow_wildcard:
            return cron_dow in self.day_of_week
        return True


def parse_cron(expression: str) -> CronSpec:
    """Parse a five-field cron expression into a :class:`CronSpec`."""
    parts = expression.split()
    if len(parts) != 5:
        raise ScheduleError(f"cron expression must have 5 fields, got {len(parts)}: {expression!r}")
    minute, _ = _parse_field(parts[0], *_FIELD_BOUNDS[0])
    hour, _ = _parse_field(parts[1], *_FIELD_BOUNDS[1])
    dom, dom_wild = _parse_field(parts[2], *_FIELD_BOUNDS[2])
    month, _ = _parse_field(parts[3], *_FIELD_BOUNDS[3])
    dow, dow_wild = _parse_field(parts[4], *_FIELD_BOUNDS[4])
    return CronSpec(
        minute=minute,
        hour=hour,
        day_of_month=dom,
        month=month,
        day_of_week=dow,
        dom_wildcard=dom_wild,
        dow_wildcard=dow_wild,
    )


def _start_of_next_month(moment: datetime) -> datetime:
    year = moment.year + (1 if moment.month == 12 else 0)
    month = 1 if moment.month == 12 else moment.month + 1
    return moment.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def cron_next(expression: str, after: datetime) -> datetime:
    """Return the first minute strictly after ``after`` matching ``expression``."""
    spec = parse_cron(expression)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(_MAX_CRON_ITERATIONS):
        if candidate.month not in spec.month:
            candidate = _start_of_next_month(candidate)
            continue
        if not spec.day_matches(candidate):
            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if candidate.hour not in spec.hour:
            candidate = (candidate + timedelta(hours=1)).replace(minute=0)
            continue
        if candidate.minute not in spec.minute:
            candidate = candidate + timedelta(minutes=1)
            continue
        return candidate
    raise ScheduleError(f"no matching time for cron {expression!r}")


def _next_hourly(after: datetime) -> datetime:
    return after.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def _next_daily(after: datetime) -> datetime:
    return after.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _next_weekly(after: datetime) -> datetime:
    day = after.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    while day.weekday() != 0:  # advance to the next Monday
        day += timedelta(days=1)
    return day


def next_run(schedule: Schedule, after: datetime) -> datetime | None:
    """Return the next run time strictly after ``after``, or ``None`` for none."""
    frequency = schedule.frequency
    if frequency is ScheduleFrequency.MANUAL:
        return None
    if frequency is ScheduleFrequency.ONCE:
        if schedule.at is None:
            return after
        try:
            at = datetime.fromisoformat(schedule.at)
        except ValueError as exc:
            raise ScheduleError(f"invalid schedule 'at' timestamp: {schedule.at!r}") from exc
        return at if at > after else None
    if frequency is ScheduleFrequency.HOURLY:
        return _next_hourly(after)
    if frequency is ScheduleFrequency.DAILY:
        return _next_daily(after)
    if frequency is ScheduleFrequency.WEEKLY:
        return _next_weekly(after)
    if schedule.expression is None:
        raise ScheduleError("cron schedule requires an 'expression'")
    return cron_next(schedule.expression, after)


def simulate(schedule: Schedule, *, start: datetime, count: int) -> list[datetime]:
    """Return up to ``count`` successive run times beginning after ``start``."""
    if count < 0:
        raise ScheduleError("simulation count must be non-negative")
    runs: list[datetime] = []
    cursor = start
    for _ in range(count):
        upcoming = next_run(schedule, cursor)
        if upcoming is None:
            break
        runs.append(upcoming)
        cursor = upcoming
    return runs


class Scheduler:
    """Thin object wrapper around the deterministic scheduling functions."""

    def next_run(self, schedule: Schedule, after: datetime) -> datetime | None:
        """Return the next run time after ``after`` (see :func:`next_run`)."""
        return next_run(schedule, after)

    def simulate(self, schedule: Schedule, *, start: datetime, count: int) -> list[datetime]:
        """Return up to ``count`` run times from ``start`` (see :func:`simulate`)."""
        return simulate(schedule, start=start, count=count)
