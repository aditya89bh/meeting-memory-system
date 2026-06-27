"""Tests for backup/restore/snapshot recovery and failure handling (Phase 9)."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from meeting_memory.exceptions import BackupError, MeetingMemoryError
from meeting_memory.recovery import (
    BackupManager,
    export_snapshot,
    file_checksum,
    import_snapshot,
    validate_database,
    verify_snapshot,
)
from meeting_memory.recovery.snapshot import Snapshot
from meeting_memory.services import MeetingService, RetrievalService
from meeting_memory.storage import SQLiteMemoryStore
from ops_helpers import build_db


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return build_db(tmp_path)


# -- checksums and validation -------------------------------------------------


def test_file_checksum_missing(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        file_checksum(tmp_path / "nope.bin")


def test_validate_missing(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        validate_database(tmp_path / "nope.db")


def test_validate_ok(db: Path) -> None:
    report = validate_database(db)
    assert report.ok and report.integrity == "ok"
    assert report.meetings == 6
    assert report.to_dict()["memories"] == report.memories


def test_validate_reports_missing_tables(tmp_path: Path) -> None:
    other = tmp_path / "foreign.db"
    connection = sqlite3.connect(other)
    connection.execute("CREATE TABLE unrelated (x INTEGER)")
    connection.commit()
    connection.close()
    report = validate_database(other)
    assert not report.ok
    assert any("missing table" in message for message in report.messages)


# -- physical backup / restore ------------------------------------------------


def test_backup_and_restore(tmp_path: Path, db: Path) -> None:
    backup = tmp_path / "copy.db"
    manifest = BackupManager(db).backup(backup)
    assert manifest.checksum == file_checksum(backup)
    assert manifest.meetings == 6
    assert manifest.to_dict()["memories"] == manifest.memories

    restored = tmp_path / "restored.db"
    report = BackupManager(restored).restore(backup)
    assert report.ok
    assert report.meetings == manifest.meetings


def test_backup_missing_source(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        BackupManager(tmp_path / "missing.db").backup(tmp_path / "out.db")


def test_restore_missing_backup(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        BackupManager(tmp_path / "target.db").restore(tmp_path / "missing.bak")


def test_restore_refuses_corrupt_backup(tmp_path: Path, db: Path) -> None:
    # A valid SQLite file that lacks our tables fails validation.
    bad = tmp_path / "bad.db"
    connection = sqlite3.connect(bad)
    connection.execute("CREATE TABLE unrelated (x INTEGER)")
    connection.commit()
    connection.close()
    with pytest.raises(BackupError, match="corrupt"):
        BackupManager(tmp_path / "target.db").restore(bad)


def test_restore_skips_verification(tmp_path: Path, db: Path) -> None:
    backup = tmp_path / "copy.db"
    BackupManager(db).backup(backup)
    report = BackupManager(tmp_path / "restored.db").restore(backup, verify=False)
    assert report.ok


def test_database_recovery_after_corruption(tmp_path: Path, db: Path) -> None:
    backup = tmp_path / "copy.db"
    BackupManager(db).backup(backup)
    # Corrupt the live database, then recover it from the backup.
    db.write_bytes(b"not a database at all")
    report = BackupManager(db).restore(backup)
    assert report.ok
    assert report.meetings == 6


# -- logical snapshots --------------------------------------------------------


def test_snapshot_round_trip(tmp_path: Path, db: Path) -> None:
    snapshot = export_snapshot(db, tmp_path / "snap.json")
    assert verify_snapshot(snapshot)
    report = import_snapshot(tmp_path / "snap.json", tmp_path / "rebuilt.db")
    assert report.ok
    assert report.meetings == 6
    assert MeetingService(tmp_path / "rebuilt.db").stats().memories == report.memories


def test_export_snapshot_without_destination(db: Path) -> None:
    snapshot = export_snapshot(db)
    assert len(snapshot.meetings) == 6
    assert snapshot.version == 1


def test_export_snapshot_missing_db(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        export_snapshot(tmp_path / "missing.db")


def test_snapshot_serialisation_round_trip(db: Path) -> None:
    snapshot = export_snapshot(db)
    restored = Snapshot.from_dict(snapshot.to_dict())
    assert restored.checksum == snapshot.checksum
    assert "meetings" in snapshot.to_json()


def test_snapshot_from_dict_missing_field() -> None:
    with pytest.raises(BackupError, match="missing required field"):
        Snapshot.from_dict({"version": 1})


def test_import_rejects_checksum_mismatch(db: Path, tmp_path: Path) -> None:
    snapshot = export_snapshot(db)
    tampered = Snapshot(
        version=snapshot.version,
        schema_version=snapshot.schema_version,
        created_at=snapshot.created_at,
        meetings=snapshot.meetings,
        memories=snapshot.memories,
        checksum="0" * 64,
    )
    with pytest.raises(BackupError, match="checksum mismatch"):
        import_snapshot(tampered, tmp_path / "x.db")


def test_import_malformed_records(tmp_path: Path) -> None:
    snapshot = Snapshot(
        version=1,
        schema_version=2,
        created_at="2025-01-01T00:00:00+00:00",
        meetings=(),
        memories=({"memory_id": "m1"},),  # missing required fields
        checksum="ignored",
    )
    with pytest.raises(BackupError, match="malformed"):
        import_snapshot(snapshot, tmp_path / "x.db", verify=False)


def test_import_handles_optional_meeting_duration(tmp_path: Path) -> None:
    meeting = {
        "meeting_id": "m1",
        "transcript_hash": "h1",
        "created_at": "2025-01-01T00:00:00+00:00",
        "title": "T",
        "date": "2025-01-01",
        "source": None,
        "duration_seconds": None,
        "participants": ["Ann"],
    }
    snapshot = Snapshot(
        version=1,
        schema_version=2,
        created_at="2025-01-01T00:00:00+00:00",
        meetings=(meeting,),
        memories=(),
        checksum="ignored",
    )
    report = import_snapshot(snapshot, tmp_path / "x.db", verify=False)
    assert report.meetings == 1


def test_snapshot_preserves_supersession(tmp_path: Path, db: Path) -> None:
    with SQLiteMemoryStore(db) as store:
        memories = store.list(limit=2)
        store.supersede(memories[0].memory_id, memories[1].memory_id)
    snapshot = export_snapshot(db)
    report = import_snapshot(snapshot, tmp_path / "rebuilt.db")
    assert report.ok
    with SQLiteMemoryStore(tmp_path / "rebuilt.db") as store:
        restored = store.get(memories[0].memory_id)
    assert restored.superseded_by == memories[1].memory_id


# -- load and failure scenarios ----------------------------------------------


def test_large_import(tmp_path: Path) -> None:
    db = build_db(tmp_path, dataset="medium", name="large.db")
    stats = MeetingService(db).stats()
    assert stats.meetings == 40
    assert stats.memories > 100


def test_repeated_import_is_idempotent(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    from meeting_memory.benchmarks import get_preset, write_dataset

    write_dataset(get_preset("small"), data_dir)
    db = tmp_path / "repeat.db"
    first = MeetingService(db).import_path(data_dir, recursive=True)
    second = MeetingService(db).import_path(data_dir, recursive=True)
    assert first.meetings_imported == 6
    assert second.meetings_imported == 0
    assert MeetingService(db).stats().meetings == 6


def test_corrupted_file_is_reported_not_fatal(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "bad.txt").write_text("this is not a transcript\n", encoding="utf-8")
    result = MeetingService(tmp_path / "x.db").import_path(data_dir, recursive=True)
    assert result.status == "failure"
    assert result.errors


def test_interrupted_then_resumed_import(tmp_path: Path) -> None:
    from meeting_memory.benchmarks import generate_dataset, get_preset

    meetings = generate_dataset(get_preset("small"))
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Simulate an interrupted import: write only the first half, import, then
    # write the rest and import again. The final state must be consistent.
    half = len(meetings) // 2
    for meeting in meetings[:half]:
        (data_dir / meeting.filename).write_text(meeting.content, encoding="utf-8")
    db = tmp_path / "resume.db"
    MeetingService(db).import_path(data_dir, recursive=True)
    for meeting in meetings[half:]:
        (data_dir / meeting.filename).write_text(meeting.content, encoding="utf-8")
    MeetingService(db).import_path(data_dir, recursive=True)
    assert MeetingService(db).stats().meetings == len(meetings)


def test_connector_failure_on_missing_path(tmp_path: Path) -> None:
    with pytest.raises(MeetingMemoryError):
        MeetingService(tmp_path / "x.db").import_path(tmp_path / "nope", recursive=True)


def test_concurrent_reads(db: Path) -> None:
    errors: list[Exception] = []

    def reader() -> None:
        try:
            from meeting_memory.retrieval import RetrievalQuery

            for _ in range(5):
                RetrievalService(db).search(RetrievalQuery(text="risk", limit=10))
        except Exception as exc:  # pragma: no cover - only on unexpected failure
            errors.append(exc)

    threads = [threading.Thread(target=reader) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors


def test_api_stress(db: Path) -> None:
    from api_helpers import make_client

    client = make_client(db)
    for _ in range(30):
        response = client.get("/search", params={"q": "risk", "limit": 5})  # type: ignore[attr-defined]
        assert response.status_code == 200
