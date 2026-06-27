"""Tests for the deterministic file import connectors."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from connector_helpers import (
    CSV_TRANSCRIPT,
    JSON_TRANSCRIPT,
    MD_TRANSCRIPT,
    TXT_TRANSCRIPT,
    fake_clock,
    write_transcripts,
)
from meeting_memory.connectors import (
    ConnectorStatus,
    ImportRequest,
    StructuredLogger,
    csv_to_transcript,
    default_manager,
    markdown_to_transcript,
)
from meeting_memory.connectors.importers import (
    ArchiveImportConnector,
    BatchImportConnector,
    CsvImportConnector,
    DirectoryImportConnector,
    JsonImportConnector,
    MarkdownImportConnector,
    TextImportConnector,
)
from meeting_memory.exceptions import ConnectorValidationError
from meeting_memory.storage import SQLiteMemoryStore

NOW = "2026-02-16T09:00:00+00:00"


def _store() -> SQLiteMemoryStore:
    return SQLiteMemoryStore(":memory:")


def test_text_import_executes(tmp_path: Path) -> None:
    path = tmp_path / "m.txt"
    path.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    connector = TextImportConnector()
    with _store() as store:
        result = connector.execute(ImportRequest(source=str(path), now=NOW), store)
        assert result.status is ConnectorStatus.SUCCESS
        assert result.meetings_imported == 1
        assert result.memories_stored > 0
        assert len(store.list_meetings()) == 1


def test_json_import_executes(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    path.write_text(JSON_TRANSCRIPT, encoding="utf-8")
    with _store() as store:
        result = JsonImportConnector().execute(ImportRequest(source=str(path), now=NOW), store)
        assert result.status is ConnectorStatus.SUCCESS
        assert result.memories_stored > 0


def test_markdown_import_executes(tmp_path: Path) -> None:
    path = tmp_path / "m.md"
    path.write_text(MD_TRANSCRIPT, encoding="utf-8")
    with _store() as store:
        result = MarkdownImportConnector().execute(ImportRequest(source=str(path), now=NOW), store)
        assert result.status is ConnectorStatus.SUCCESS
        assert result.memories_stored > 0


def test_csv_import_executes(tmp_path: Path) -> None:
    path = tmp_path / "m.csv"
    path.write_text(CSV_TRANSCRIPT, encoding="utf-8")
    with _store() as store:
        result = CsvImportConnector().execute(ImportRequest(source=str(path), now=NOW), store)
        assert result.status is ConnectorStatus.SUCCESS
        assert result.memories_stored > 0


def test_single_file_validation(tmp_path: Path) -> None:
    connector = TextImportConnector()
    missing = connector.validate(ImportRequest(source=str(tmp_path / "missing.txt")))
    assert any("does not exist" in problem for problem in missing)

    directory = connector.validate(ImportRequest(source=str(tmp_path)))
    assert any("not a file" in problem for problem in directory)

    wrong = tmp_path / "m.json"
    wrong.write_text(JSON_TRANSCRIPT, encoding="utf-8")
    bad_ext = connector.validate(ImportRequest(source=str(wrong)))
    assert any("not a text file" in problem for problem in bad_ext)


def test_dry_run_does_not_persist(tmp_path: Path) -> None:
    path = tmp_path / "m.txt"
    path.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    result = TextImportConnector().dry_run(ImportRequest(source=str(path), dry_run=True))
    assert result.status is ConnectorStatus.DRY_RUN
    assert result.dry_run is True
    assert result.memories_stored > 0


def test_duplicate_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "m.txt"
    path.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    connector = TextImportConnector()
    with _store() as store:
        first = connector.execute(ImportRequest(source=str(path), now=NOW), store)
        second = connector.execute(ImportRequest(source=str(path), now=NOW), store)
    assert first.duplicates == 0
    assert second.duplicates == 1
    assert second.outcomes[0].status is ConnectorStatus.SKIPPED


def test_malformed_file_is_graceful(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")
    with _store() as store:
        result = JsonImportConnector().execute(ImportRequest(source=str(path)), store)
    assert result.status is ConnectorStatus.FAILURE
    assert result.errors
    assert result.outcomes[0].error is not None


def test_unknown_memory_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "m.txt"
    path.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    request = ImportRequest(source=str(path), memory_types=frozenset({"bogus"}))
    with _store() as store, pytest.raises(ConnectorValidationError):
        TextImportConnector().execute(request, store)


def test_directory_import_with_limit_and_logger(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    logger = StructuredLogger("cid", clock=fake_clock())
    with _store() as store:
        result = DirectoryImportConnector().execute(
            ImportRequest(source=str(source), now=NOW, limit=2), store, logger=logger
        )
    assert result.files_processed == 2
    assert result.duration_ms >= 0.0
    assert logger.records()


def test_directory_empty_warns(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with _store() as store:
        result = DirectoryImportConnector().execute(ImportRequest(source=str(empty)), store)
    assert result.files_processed == 0
    assert any("no matching files" in warning for warning in result.warnings)


def test_directory_validation(tmp_path: Path) -> None:
    connector = DirectoryImportConnector()
    missing = connector.validate(ImportRequest(source=str(tmp_path / "nope")))
    assert any("does not exist" in problem for problem in missing)
    a_file = tmp_path / "m.txt"
    a_file.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    not_dir = connector.validate(ImportRequest(source=str(a_file)))
    assert any("not a directory" in problem for problem in not_dir)


def test_recursive_directory(tmp_path: Path) -> None:
    write_transcripts(tmp_path / "data")
    nested = tmp_path / "data" / "nested"
    nested.mkdir()
    (nested / "deep.txt").write_text(TXT_TRANSCRIPT, encoding="utf-8")
    with _store() as store:
        flat = DirectoryImportConnector().execute(
            ImportRequest(source=str(tmp_path / "data"), now=NOW), store
        )
    with _store() as store2:
        deep = DirectoryImportConnector().execute(
            ImportRequest(source=str(tmp_path / "data"), now=NOW, recursive=True), store2
        )
    assert deep.files_processed == flat.files_processed + 1


def test_batch_import_and_validation(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    connector = BatchImportConnector()
    request = ImportRequest(
        source="",
        sources=(str(source / "a.txt"), str(source / "b.json")),
        now=NOW,
    )
    with _store() as store:
        result = connector.execute(request, store)
    assert result.files_processed == 2

    empty_problems = connector.validate(ImportRequest(source=""))
    assert any("non-empty" in problem for problem in empty_problems)

    bad = connector.validate(
        ImportRequest(source="", sources=(str(source / "missing.txt"), str(source)))
    )
    assert any("does not exist" in problem for problem in bad)


def test_batch_dry_run(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    result = BatchImportConnector().dry_run(
        ImportRequest(source="", sources=(str(source / "a.txt"),), dry_run=True)
    )
    assert result.status is ConnectorStatus.DRY_RUN


def test_archive_import(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.txt", TXT_TRANSCRIPT)
        zf.writestr("b.json", JSON_TRANSCRIPT)
        zf.writestr("ignore.rst", "not a transcript")
    connector = ArchiveImportConnector()
    with _store() as store:
        result = connector.execute(ImportRequest(source=str(archive), now=NOW), store)
    assert result.files_processed == 2
    assert all(outcome.path.startswith("bundle.zip:") for outcome in result.outcomes)


def test_archive_dry_run_and_validation(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.txt", TXT_TRANSCRIPT)
    result = ArchiveImportConnector().dry_run(ImportRequest(source=str(archive), dry_run=True))
    assert result.status is ConnectorStatus.DRY_RUN

    connector = ArchiveImportConnector()
    not_zip = tmp_path / "plain.txt"
    not_zip.write_text("hello", encoding="utf-8")
    problems = connector.validate(ImportRequest(source=str(not_zip)))
    assert any("not a zip archive" in problem for problem in problems)
    assert connector.validate(ImportRequest(source=str(tmp_path / "missing.zip")))


def test_manager_import_directory(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    manager = default_manager()
    with _store() as store:
        result = manager.import_source(ImportRequest(source=str(source), now=NOW), store)
    assert result.files_processed == 4


def test_markdown_to_transcript_strips_markup() -> None:
    text = markdown_to_transcript(MD_TRANSCRIPT)
    assert "Alice: We decided to freeze scope for the release." in text
    assert "# Agenda" not in text


def test_csv_to_transcript_builds_turns() -> None:
    text = csv_to_transcript(CSV_TRANSCRIPT)
    assert text.startswith("Alice: We decided")
    assert "Bob: I will build the dashboard" in text


def test_csv_to_transcript_skips_incomplete_rows() -> None:
    text = csv_to_transcript("owner,action\nAlice,\n,do something\nBob,real action\n")
    assert text == "Bob: real action"
