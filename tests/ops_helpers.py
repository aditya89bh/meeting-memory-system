"""Shared helpers for Phase 9 (operations) tests."""

from __future__ import annotations

from pathlib import Path

from meeting_memory.benchmarks import get_preset, write_dataset
from meeting_memory.services import MeetingService


def build_db(tmp_path: Path, *, dataset: str = "small", name: str = "ops.db") -> Path:
    """Generate ``dataset`` into a temp directory and import it into a database."""
    data_dir = tmp_path / "dataset"
    write_dataset(get_preset(dataset), data_dir)
    db = tmp_path / name
    MeetingService(db).import_path(data_dir, recursive=True)
    return db
