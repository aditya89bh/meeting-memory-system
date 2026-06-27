#!/usr/bin/env python
"""Demonstrate the replay engine over a freshly generated dataset.

Builds a temporary database from the small dataset, then replays it in several
ways: everything, by project, by person, and step-by-step. Everything is
deterministic and self-contained (uses a temporary directory).
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from meeting_memory.benchmarks import get_preset, write_dataset
from meeting_memory.replay import ReplayEngine, ReplayFilter
from meeting_memory.services import MeetingService


def main() -> int:
    """Generate data, then replay it all, by project, by person, and stepwise."""
    with TemporaryDirectory(prefix="mm-replay-") as tmp:
        data_dir = Path(tmp) / "data"
        write_dataset(get_preset("small"), data_dir)
        db = Path(tmp) / "replay.db"
        MeetingService(db).import_path(data_dir, recursive=True)

        engine = ReplayEngine(db)

        all_run = engine.replay_all()
        print(f"All meetings: {all_run.steps_played} steps, {all_run.memories_played} memories")

        atlas = engine.timeline(ReplayFilter(project="Atlas"))
        print(f"Project Atlas: {atlas.meeting_count} meetings, range {atlas.date_range}")

        priya = engine.timeline(ReplayFilter(person="Priya"))
        print(f"Person Priya: {priya.meeting_count} meetings")

        print("Step-by-step:")
        session = engine.session(speed=2.0, step_delay=0.0)
        while session.has_next():
            event = session.step()
            print(
                f"  step {session.position}: {event.meeting.title} "
                f"(+{len(event.memories)} memories)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
