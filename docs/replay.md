# Replay

The replay engine reconstructs the chronological timeline of stored meetings and
the memories they produced, then plays them back in order. It is **read-only and
deterministic**: the same store and filter always yield the same timeline.

## Concepts

| Type | Role |
| --- | --- |
| `ReplayFilter` | A deterministic selection: project, person, date, or date range. |
| `ReplayEvent` | One step: a meeting plus the memories it contributed, with running totals. |
| `ReplayTimeline` | The ordered events for a filter, with date range and counts. |
| `ReplaySession` | A stateful cursor over a timeline with speed/step controls. |
| `ReplayResult` | The outcome of a (full or partial) run. |
| `ReplayEngine` | Entry point bound to a database. |

## CLI

```bash
# Replay everything (summary of steps + cumulative memory counts by type)
meeting-memory replay --db atlas.db

# Print the reconstructed timeline instead of running it
meeting-memory replay --db atlas.db --timeline

# Filter by project, person, a single date, or a range
meeting-memory replay --db atlas.db --project Atlas
meeting-memory replay --db atlas.db --person Priya
meeting-memory replay --db atlas.db --date 2025-01-06
meeting-memory replay --db atlas.db --from 2025-01-06 --to 2025-02-01

# Speed multiplier and JSON output
meeting-memory replay --db atlas.db --speed 4 --step-delay 0.1 --json
```

## Python

```python
from meeting_memory.replay import ReplayEngine, ReplayFilter

engine = ReplayEngine("atlas.db")

# Whole-timeline replay
result = engine.replay_all()
print(result.steps_played, result.memories_played, result.final_by_type)

# Filtered timelines
atlas = engine.timeline(ReplayFilter(project="Atlas"))
print(atlas.meeting_count, atlas.date_range)

# Step-by-step control
session = engine.session(speed=2.0, step_delay=0.0)
while session.has_next():
    event = session.step()
    print(event.index, event.meeting.title, len(event.memories))

session.reset()      # rewind to the start
session.seek(3)      # jump to a position (0 = before the first event)
```

## Filtering semantics

- **project** — matches case-insensitively against the meeting title and the text
  of its memories (so a project named in a decision is found even if it is not in
  the title).
- **person** — matches against the meeting participants and memory speakers.
- **date / date_from / date_to** — compared against each meeting's date; meetings
  without a date are excluded from range filters.

Events are ordered by `(date, meeting_id)` and memories within an event by
`(utterance_index, memory_id)`, so timelines are stable and reproducible.

## Speed control

`ReplaySession` sleeps `step_delay / speed` seconds between steps. The default
`step_delay` is `0.0` (no waiting). A custom `sleeper` and `clock` can be
injected to keep tests instantaneous and deterministic.
