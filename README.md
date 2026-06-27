# Meeting Memory System

A robust ingestion and parsing layer that converts raw meeting transcripts into
a clean, typed, structured internal representation.

> **Phase 1 scope.** This phase covers **parsing and normalization only**. It
> deliberately performs **no** AI extraction (no decisions, tasks, or
> summaries). Its sole responsibility is turning raw transcripts into a faithful
> structured model that later phases can build on.

## Features

- **Typed domain models** for meetings, speakers, utterances, timestamps, and
  metadata (`Meeting`, `Speaker`, `Utterance`, `Timestamp`, `Metadata`).
- **Extensible transcript loader** supporting `.txt` and `.json`, with a small
  registry so new on-disk formats can be added without touching the parser.
- **Format-aware parser** that understands speaker labels, leading/trailing
  timestamps, multi-line utterances, and an optional metadata front-matter block.
- **Semantic validation** with descriptive exceptions for empty meetings,
  duplicate timestamps, and invalid speakers.
- **Normalization utilities** that clean whitespace, line endings, speaker
  labels, and timestamp formatting without changing semantic content.
- **Statistics helpers** for utterance/speaker/word counts and meeting duration.
- **A command-line interface** that emits structured JSON.
- **100% test coverage**, fully type-checked (`mypy --strict`) and linted (`ruff`).

## Installation

The project targets Python 3.10+ and uses a standard `pyproject.toml`.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package (add the dev extra for tests/linting/type-checking)
pip install -e ".[dev]"
```

## Quick start

### Command line

```bash
# Parse a transcript and print structured JSON
meeting-memory parse meeting.txt

# Include descriptive statistics and write the result to a file
meeting-memory parse meeting.json --stats --output meeting.parsed.json

# Skip semantic validation, or allow duplicate timestamps
meeting-memory parse meeting.txt --no-validate
meeting-memory parse meeting.json --allow-duplicate-timestamps
```

### Library

```python
from meeting_memory.parser import parse_file, parse_text, validate_meeting
from meeting_memory.utils import compute_statistics

meeting = parse_file("meeting.txt")
validate_meeting(meeting)  # raises a ValidationError subclass if invalid

for utterance in meeting:
    stamp = utterance.timestamp.label if utterance.timestamp else "--:--:--"
    print(f"[{stamp}] {utterance.speaker.name}: {utterance.text}")

stats = compute_statistics(meeting)
print(stats.speaker_utterance_counts)
```

## Supported transcript formats

### Plain text

Each turn is a line of the form `Speaker: text`. Timestamps may lead or trail the
speaker label, and lines that do not start a new turn are merged into the
previous utterance as continuations. An optional `---` delimited front-matter
block at the top carries metadata.

```text
---
title: Weekly Sync
date: 2026-06-27
team: Apollo
---
[00:00:05] Alice: Hello everyone, thanks for joining.
Bob [00:00:12]: Hi Alice — quick note before we start,
this line continues Bob's previous utterance.
Carol: No timestamp here, and that's fine.
```

All of the following timestamp shapes are recognised:

| Example                 | Meaning                          |
| ----------------------- | -------------------------------- |
| `[00:01:05] Alice: ...` | leading, bracketed `HH:MM:SS`    |
| `Alice [00:01:05]: ...` | trailing, bracketed              |
| `Alice 00:01:05: ...`   | trailing, plain                  |
| `Alice 02:30: ...`      | `MM:SS` (interpreted as minutes) |

### JSON

A JSON object with an `utterances` array (or a bare array of utterance objects).
Speaker, text, and timestamp fields accept a few common aliases.

```json
{
  "title": "Standup",
  "date": "2026-06-27",
  "metadata": { "room": "A1" },
  "utterances": [
    { "speaker": "Carol", "text": "Morning all.", "timestamp": "00:00:05" },
    { "name": "Dave", "content": "Hi", "time": 65 }
  ]
}
```

- Speaker keys: `speaker`, `name`, `speaker_name`
- Text keys: `text`, `utterance`, `content`, `message`
- Timestamp keys: `timestamp`, `time`, `start` — a string (`"00:01:05"`) or a
  number of seconds (`65`).

## Output shape

`meeting-memory parse` emits a JSON document like:

```json
{
  "metadata": {
    "title": "Weekly Sync",
    "date": "2026-06-27",
    "source_path": "meeting.txt",
    "source_format": "txt",
    "extra": { "team": "Apollo" }
  },
  "speakers": ["Alice", "Bob", "Carol"],
  "utterances": [
    {
      "index": 0,
      "speaker": "Alice",
      "text": "Hello everyone, thanks for joining.",
      "timestamp": { "total_seconds": 5.0, "label": "00:00:05" }
    }
  ]
}
```

With `--stats`, a `"statistics"` object is added containing utterance, speaker,
and word counts plus the meeting duration.

## Architecture overview

The package follows a clean, layered structure under `src/meeting_memory/`:

```
meeting_memory/
├── models/        # Typed domain models (Meeting, Speaker, Utterance, ...)
├── io/            # Transcript loading from disk (extensible format registry)
├── parser/        # Parsing raw content into meetings, plus validation
├── utils/         # Normalization and statistics helpers
├── exceptions/    # Exception hierarchy rooted at MeetingMemoryError
└── cli.py         # Command-line entry point
```

Data flows in one direction:

```
file ──▶ io.load_transcript ──▶ RawTranscript ──▶ parser.parse ──▶ Meeting
                                                          │
                                       utils.normalize_* ─┘
Meeting ──▶ parser.validate_meeting        (semantic checks)
Meeting ──▶ utils.compute_statistics       (descriptive metrics)
```

- **Loading is decoupled from parsing.** The loader only reads and decodes a
  file; the parser interprets the decoded content. Adding a new format means
  registering a reader callable — no parser changes required.
- **Models are immutable.** All domain models are frozen dataclasses, so a parsed
  `Meeting` is a stable, hashable value object.
- **Errors are specific.** Every failure raises a descriptive subclass of
  `MeetingMemoryError`, distinguishing load, parse, and validation problems.

## Development

```bash
ruff check .          # lint
ruff format .         # format
mypy                  # strict type checking
pytest --cov          # run tests with coverage
```

## License

MIT
