"""Stateful, controllable replay sessions."""

from __future__ import annotations

import time
from collections.abc import Callable

from ..exceptions import ReplayError
from .models import ReplayEvent, ReplayResult, ReplayTimeline


class ReplaySession:
    """Step through a :class:`ReplayTimeline` with speed control.

    The session is deterministic: stepping yields events in timeline order. The
    optional ``step_delay`` (scaled by ``speed``) is the only timing knob, and a
    custom ``sleeper`` can be injected to keep tests instantaneous.
    """

    def __init__(
        self,
        timeline: ReplayTimeline,
        *,
        speed: float = 1.0,
        step_delay: float = 0.0,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if speed <= 0:
            raise ReplayError(f"speed must be positive, got {speed!r}")
        if step_delay < 0:
            raise ReplayError(f"step_delay must be non-negative, got {step_delay!r}")
        self.timeline = timeline
        self.speed = speed
        self.step_delay = step_delay
        self._sleeper = sleeper
        self._clock = clock
        self._position = 0
        self._elapsed = 0.0

    @property
    def position(self) -> int:
        """Return the number of events already played."""
        return self._position

    @property
    def remaining(self) -> int:
        """Return the number of events still to play."""
        return len(self.timeline.events) - self._position

    @property
    def elapsed_seconds(self) -> float:
        """Return the cumulative wall-clock time spent playing events."""
        return self._elapsed

    @property
    def current(self) -> ReplayEvent | None:
        """Return the most recently played event, or ``None`` before the start."""
        if self._position == 0:
            return None
        return self.timeline.events[self._position - 1]

    def has_next(self) -> bool:
        """Return whether another event can be played."""
        return self._position < len(self.timeline.events)

    def reset(self) -> None:
        """Rewind the session to before the first event."""
        self._position = 0
        self._elapsed = 0.0

    def seek(self, index: int) -> None:
        """Move the playhead to ``index`` (0 = before the first event)."""
        if not 0 <= index <= len(self.timeline.events):
            raise ReplayError(f"cannot seek to {index}; timeline has {len(self.timeline.events)}")
        self._position = index

    def step(self) -> ReplayEvent:
        """Play and return the next event, honouring the (scaled) step delay."""
        if not self.has_next():
            raise ReplayError("replay session is exhausted")
        if self.step_delay > 0:
            start = self._clock()
            self._sleeper(self.step_delay / self.speed)
            self._elapsed += self._clock() - start
        event = self.timeline.events[self._position]
        self._position += 1
        return event

    def run(self) -> ReplayResult:
        """Play every remaining event and return a :class:`ReplayResult`."""
        start = self._clock()
        while self.has_next():
            self.step()
        self._elapsed = max(self._elapsed, self._clock() - start)
        final = self.current
        final_by_type = dict(final.cumulative_by_type) if final is not None else {}
        return ReplayResult(
            timeline=self.timeline,
            steps_played=self._position,
            elapsed_seconds=self._elapsed,
            speed=self.speed,
            final_by_type=final_by_type,
        )
