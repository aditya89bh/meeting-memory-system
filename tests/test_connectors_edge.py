"""Edge-case and branch-coverage tests for the connector framework."""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from connector_helpers import TXT_TRANSCRIPT, fake_clock, write_transcripts
from meeting_memory.connectors import (
    AutomationEngine,
    ConnectorStatus,
    ExportRequest,
    ImportRequest,
    LogLevel,
    LogRecord,
    Schedule,
    ScheduleFrequency,
    StructuredLogger,
    build_job,
    importers,
    next_run,
    read_logs,
    validate_job,
)
from meeting_memory.connectors.automation import JobHistory
from meeting_memory.connectors.config import parse_yaml
from meeting_memory.connectors.exporters import JsonExportConnector, _BaseExportConnector
from meeting_memory.connectors.importers import (
    ArchiveImportConnector,
    BatchImportConnector,
    DirectoryImportConnector,
    TextImportConnector,
    markdown_to_transcript,
)
from meeting_memory.connectors.logging import JsonlFileLogSink, LogSink
from meeting_memory.connectors.scheduler import _parse_field, parse_cron
from meeting_memory.exceptions import PipelineConfigError, ScheduleError
from meeting_memory.storage import SQLiteMemoryStore

FIXED = datetime(2026, 6, 27, 14, 30)


# --- config / YAML parser ------------------------------------------------


def test_yaml_single_quote_keeps_hash() -> None:
    data = parse_yaml("name: 'a # b'")
    assert data == {"name": "a # b"}


def test_yaml_sequence_then_key() -> None:
    data = parse_yaml("steps:\n- type: graph\nname: x\n")
    assert data == {"steps": [{"type": "graph"}], "name": "x"}


def test_yaml_empty_sequence_items() -> None:
    data = parse_yaml("matrix:\n  -\n    a: 1\n  -\n")
    assert data == {"matrix": [{"a": 1}, None]}


def test_yaml_unexpected_indentation() -> None:
    with pytest.raises(PipelineConfigError):
        parse_yaml("a: 1\n  b: 2\n")


def test_yaml_trailing_empty_key() -> None:
    assert parse_yaml("a:\n") == {"a": None}


def test_validate_job_requires_steps() -> None:
    problems = validate_job(build_job({"name": "p", "steps": []}))
    assert any("at least one step" in problem for problem in problems)


def test_load_pipeline_rejects_invalid(tmp_path: Path) -> None:
    from meeting_memory.connectors import load_pipeline

    config = tmp_path / "bad.yaml"
    # Builds successfully but fails validation (export step missing 'format').
    config.write_text("name: p\nsteps:\n  - type: export\n", encoding="utf-8")
    with pytest.raises(PipelineConfigError, match="invalid pipeline configuration"):
        load_pipeline(config)


# --- importers -----------------------------------------------------------


def test_markdown_without_front_matter_drops_prose() -> None:
    text = "# Heading\n- Just some prose without a colon\n- Alice: We decided to ship.\n"
    out = markdown_to_transcript(text)
    assert "Alice: We decided to ship." in out
    assert "prose" not in out


def test_markdown_unterminated_front_matter() -> None:
    text = "---\ntitle: x\nAlice: We decided to ship.\n"
    out = markdown_to_transcript(text)
    assert "Alice: We decided to ship." in out


def test_process_file_handles_os_error(tmp_path: Path) -> None:
    source = importers._FileSource(path=tmp_path / "missing.txt", fmt="text", label="missing.txt")
    outcome = importers._process_file(
        source,
        store=None,
        config=importers.ExtractionConfig(),
        created_at=datetime(2026, 2, 16, tzinfo=timezone.utc),
        deduplicate=False,
        dry_run=True,
    )
    assert outcome.status is ConnectorStatus.FAILURE
    assert outcome.error


def test_single_file_validate_accepts_match(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    assert TextImportConnector().validate(ImportRequest(source=str(path))) == []


def test_directory_validate_accepts_dir(tmp_path: Path) -> None:
    assert DirectoryImportConnector().validate(ImportRequest(source=str(tmp_path))) == []


def test_batch_validate_flags_unsupported(tmp_path: Path) -> None:
    good = tmp_path / "a.txt"
    good.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    bad = tmp_path / "a.xml"
    bad.write_text("<x/>", encoding="utf-8")
    problems = BatchImportConnector().validate(
        ImportRequest(source="", sources=(str(good), str(bad)))
    )
    assert any("unsupported file" in problem for problem in problems)


def test_batch_gather_skips_and_limits(tmp_path: Path) -> None:
    good = tmp_path / "a.txt"
    good.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    other = tmp_path / "b.txt"
    other.write_text(TXT_TRANSCRIPT, encoding="utf-8")
    bad = tmp_path / "a.xml"
    bad.write_text("<x/>", encoding="utf-8")
    request = ImportRequest(
        source="", sources=(str(good), str(bad), str(other)), limit=1, dry_run=True
    )
    result = BatchImportConnector().dry_run(request)
    assert result.files_processed == 1


def test_archive_validate_rejects_directory(tmp_path: Path) -> None:
    problems = ArchiveImportConnector().validate(ImportRequest(source=str(tmp_path)))
    assert any("not a file" in problem for problem in problems)


def _make_archive(tmp_path: Path) -> Path:
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.txt", TXT_TRANSCRIPT)
        zf.writestr("b.txt", TXT_TRANSCRIPT)
    return archive


def test_archive_validate_accepts_zip(tmp_path: Path) -> None:
    archive = _make_archive(tmp_path)
    assert ArchiveImportConnector().validate(ImportRequest(source=str(archive))) == []


def test_archive_import_respects_limit(tmp_path: Path) -> None:
    archive = _make_archive(tmp_path)
    request = ImportRequest(source=str(archive), limit=1, dry_run=True)
    result = ArchiveImportConnector().dry_run(request)
    assert result.files_processed == 1


# --- logging -------------------------------------------------------------


def test_log_level_str() -> None:
    assert str(LogLevel.INFO) == "info"


def test_base_log_sink_is_abstract() -> None:
    record = LogRecord(correlation_id="cid", sequence=1, level=LogLevel.INFO, message="m")
    with pytest.raises(NotImplementedError):
        LogSink().write(record)


def test_records_empty_for_file_sink(tmp_path: Path) -> None:
    logger = StructuredLogger("cid", sink=JsonlFileLogSink(tmp_path / "log.jsonl"))
    logger.emit(LogLevel.INFO, "hi")
    assert logger.records() == ()


def test_read_logs_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    path.write_text('{"correlation_id": "a", "message": "m"}\n\n', encoding="utf-8")
    records = read_logs(path)
    assert len(records) == 1


# --- scheduler -----------------------------------------------------------


def test_next_run_cron_branch() -> None:
    schedule = Schedule(ScheduleFrequency.CRON, expression="*/30 * * * *")
    assert next_run(schedule, FIXED) == datetime(2026, 6, 27, 15, 0)


def test_parse_cron_empty_token() -> None:
    with pytest.raises(ScheduleError):
        parse_cron("1,, * * * *")


def test_parse_field_rejects_empty() -> None:
    with pytest.raises(ScheduleError):
        _parse_field("", 0, 59)


# --- exporters -----------------------------------------------------------


class _DummyExport(_BaseExportConnector):
    name_id = "dummy"
    formats = ("dummy",)
    summary = "dummy"


def test_base_render_not_implemented() -> None:
    with SQLiteMemoryStore(":memory:") as store, pytest.raises(NotImplementedError):
        _DummyExport()._render(ExportRequest(fmt="dummy"), store, None)


def test_export_validate_missing_parent(tmp_path: Path) -> None:
    request = ExportRequest(fmt="json", destination=str(tmp_path / "nope" / "out.json"))
    problems = JsonExportConnector().validate(request)
    assert any("destination directory does not exist" in problem for problem in problems)


def test_export_validate_existing_parent(tmp_path: Path) -> None:
    request = ExportRequest(fmt="json", destination=str(tmp_path / "out.json"))
    assert JsonExportConnector().validate(request) == []


def test_export_to_bare_filename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = write_transcripts(tmp_path / "data")
    db = tmp_path / "atlas.db"
    with SQLiteMemoryStore(db) as store:
        from connector_helpers import populate_store

        populate_store(store, source)
    monkeypatch.chdir(tmp_path)
    with SQLiteMemoryStore(db) as store:
        request = ExportRequest(fmt="json", destination="bare.json")
        result = JsonExportConnector().execute(request, store)
    assert (tmp_path / "bare.json").exists()
    assert result.status is ConnectorStatus.SUCCESS


# --- automation ----------------------------------------------------------


def test_import_step_types_non_list(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    job = build_job(
        {
            "name": "p",
            "steps": [{"type": "import", "source": str(source), "types": "decision"}],
        }
    )
    engine = AutomationEngine(
        clock=fake_clock(), now=lambda: datetime(2026, 2, 16, tzinfo=timezone.utc)
    )
    result = engine.run_job(job, db=tmp_path / "atlas.db")
    assert result.status is ConnectorStatus.SUCCESS


def test_job_history_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "jobs.jsonl"
    path.write_text('{"job": "p", "status": "success"}\n\n', encoding="utf-8")
    assert len(JobHistory(path).list()) == 1


# --- CLI branch coverage -------------------------------------------------


def _write_pipeline(tmp_path: Path, source: Path) -> Path:
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "name: daily\nschedule:\n  frequency: daily\n"
        f"steps:\n  - type: import\n    source: {source}\n  - type: graph\n",
        encoding="utf-8",
    )
    return config


def test_cli_automate_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from meeting_memory.cli import main

    source = write_transcripts(tmp_path / "data")
    config = _write_pipeline(tmp_path, source)
    assert main(["automate", str(config), "--db", str(tmp_path / "atlas.db"), "--json"]) == 0
    import json as _json

    payload = _json.loads(capsys.readouterr().out)
    assert payload["job"] == "daily"


def test_cli_jobs_human(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from meeting_memory.cli import main

    source = write_transcripts(tmp_path / "data")
    config = _write_pipeline(tmp_path, source)
    db = tmp_path / "atlas.db"
    assert main(["automate", str(config), "--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["jobs", "--db", str(db)]) == 0
    assert "daily" in capsys.readouterr().out


def test_cli_schedule_manual_no_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from meeting_memory.cli import main

    config = tmp_path / "manual.yaml"
    config.write_text(
        "name: m\nschedule:\n  frequency: manual\nsteps:\n  - type: import\n    source: x.txt\n",
        encoding="utf-8",
    )
    assert main(["schedule", str(config)]) == 0
    assert "No upcoming runs" in capsys.readouterr().out
