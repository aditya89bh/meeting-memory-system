"""Shared builders for connector-framework tests.

These helpers write small deterministic transcripts in every supported format and
populate a store, so connector, automation, and CLI tests stay self-contained
without depending on the bundled example data.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from pathlib import Path

from meeting_memory.connectors import ImportRequest, default_manager
from meeting_memory.storage import SQLiteMemoryStore

NOW = "2026-02-16T09:00:00+00:00"

TXT_TRANSCRIPT = """---
title: Kickoff
date: 2026-02-16
---
Alice: We decided to adopt the new ingestion API.
Bob: I will own the migration by next Friday.
Alice: There is a risk the vendor rate limits will slow ingestion.
"""

JSON_TRANSCRIPT = """{
  "title": "Review",
  "date": "2026-02-17",
  "utterances": [
    {"speaker": "Alice", "text": "We decided to ship the beta this week."},
    {"speaker": "Bob", "text": "I will prepare the release notes by Monday."}
  ]
}
"""

MD_TRANSCRIPT = """---
title: Notes
date: 2026-02-18
---
# Agenda

- Alice: We decided to freeze scope for the release.
- **Bob:** I will follow up with the vendor about the risk.
"""

CSV_TRANSCRIPT = """owner,action
Alice,We decided to add a status dashboard
Bob,I will build the dashboard by next sprint
"""


def fake_clock() -> Callable[[], float]:
    """Return a deterministic monotonic-style clock advancing by 1ms per call."""
    counter = itertools.count(0, 1)
    return lambda: next(counter) * 0.001


def write_transcripts(directory: Path) -> Path:
    """Write one transcript of each supported format into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "a.txt").write_text(TXT_TRANSCRIPT, encoding="utf-8")
    (directory / "b.json").write_text(JSON_TRANSCRIPT, encoding="utf-8")
    (directory / "c.md").write_text(MD_TRANSCRIPT, encoding="utf-8")
    (directory / "d.csv").write_text(CSV_TRANSCRIPT, encoding="utf-8")
    return directory


def populate_store(store: SQLiteMemoryStore, source: Path, *, now: str = NOW) -> None:
    """Import every transcript in ``source`` into ``store``."""
    manager = default_manager()
    manager.import_source(ImportRequest(source=str(source), now=now), store)
