"""Tests for connector model value objects and their serialisation."""

from __future__ import annotations

from meeting_memory.connectors import (
    AutomationJob,
    AutomationResult,
    ConnectorCapability,
    ConnectorMetadata,
    ConnectorResult,
    ConnectorStatus,
    ConnectorType,
    ExportRequest,
    ExportResult,
    FileImportOutcome,
    ImportRequest,
    ImportResult,
    Schedule,
    ScheduleFrequency,
    StageResult,
    StepConfig,
)


def test_enum_str_values() -> None:
    assert str(ConnectorType.IMPORT) == "import"
    assert str(ConnectorStatus.SUCCESS) == "success"
    assert str(ConnectorCapability.DRY_RUN) == "dry_run"
    assert str(ScheduleFrequency.WEEKLY) == "weekly"


def test_metadata_supports_and_to_dict() -> None:
    meta = ConnectorMetadata(
        name="text",
        version="1.0",
        connector_type=ConnectorType.IMPORT,
        description="Import text.",
        capabilities=frozenset({ConnectorCapability.DRY_RUN, ConnectorCapability.VALIDATION}),
        formats=("txt",),
    )
    assert meta.supports(ConnectorCapability.DRY_RUN)
    assert not meta.supports(ConnectorCapability.ARCHIVE)
    payload = meta.to_dict()
    assert payload["capabilities"] == ["dry_run", "validation"]
    assert payload["formats"] == ["txt"]


def test_connector_result_ok_and_to_dict() -> None:
    ok = ConnectorResult(connector="x", status=ConnectorStatus.SUCCESS)
    assert ok.ok is True
    bad = ConnectorResult(connector="x", status=ConnectorStatus.FAILURE, errors=("boom",))
    assert bad.ok is False
    assert bad.to_dict()["errors"] == ["boom"]


def test_import_request_to_dict_round_trip_fields() -> None:
    request = ImportRequest(
        source="dir",
        sources=("a.txt",),
        recursive=True,
        memory_types=frozenset({"risk", "decision"}),
        limit=3,
    )
    payload = request.to_dict()
    assert payload["recursive"] is True
    assert payload["memory_types"] == ["decision", "risk"]
    assert payload["sources"] == ["a.txt"]


def test_import_result_summary_and_dict() -> None:
    outcome = FileImportOutcome(path="a.txt", status=ConnectorStatus.SUCCESS, stored=2)
    result = ImportResult(
        connector="directory",
        status=ConnectorStatus.SUCCESS,
        files_processed=1,
        meetings_imported=1,
        memories_stored=2,
        duplicates=1,
        outcomes=(outcome,),
        warnings=("w",),
        errors=("e",),
        dry_run=False,
    )
    lines = result.summary_lines()
    assert "1 files processed" in lines
    assert "1 duplicate files skipped" in lines
    assert "warning: w" in lines
    assert "error: e" in lines
    assert result.to_dict()["outcomes"][0]["path"] == "a.txt"


def test_import_result_dry_run_prefix() -> None:
    result = ImportResult(connector="text", status=ConnectorStatus.DRY_RUN, dry_run=True)
    assert result.summary_lines()[0].startswith("[dry-run] ")


def test_export_request_and_result() -> None:
    request = ExportRequest(fmt="markdown", destination="out.md", options={"k": 1})
    assert request.to_dict()["options"] == {"k": 1}
    result = ExportResult(
        connector="markdown",
        status=ConnectorStatus.SUCCESS,
        fmt="markdown",
        destination="out.md",
        items_exported=3,
        bytes_written=10,
        warnings=("w",),
        errors=("e",),
    )
    lines = result.summary_lines()
    assert "destination: out.md" in lines
    assert "10 bytes written" in lines
    assert result.to_dict()["fmt"] == "markdown"


def test_export_result_stdout_destination() -> None:
    result = ExportResult(
        connector="json", status=ConnectorStatus.DRY_RUN, fmt="json", dry_run=True
    )
    lines = result.summary_lines()
    assert "destination: stdout" in lines
    assert lines[0].startswith("[dry-run] ")


def test_automation_job_and_result_to_dict() -> None:
    job = AutomationJob(
        name="daily",
        steps=(StepConfig(type="import", params={"source": "dir"}),),
        schedule=Schedule(frequency=ScheduleFrequency.DAILY),
    )
    payload = job.to_dict()
    assert payload["schedule"]["frequency"] == "daily"
    assert payload["steps"][0]["type"] == "import"

    stage = StageResult(stage="import", status=ConnectorStatus.SUCCESS, items=2)
    result = AutomationResult(
        job="daily",
        correlation_id="abc",
        status=ConnectorStatus.SUCCESS,
        started_at="2026-02-16T09:00:00+00:00",
        finished_at="2026-02-16T09:00:01+00:00",
        stages=(stage,),
        errors=("oops",),
    )
    lines = result.summary_lines()
    assert "correlation: abc" in lines
    assert any("import" in line for line in lines)
    assert "error: oops" in lines
    assert result.to_dict()["stages"][0]["stage"] == "import"


def test_schedule_default_is_manual() -> None:
    assert Schedule().frequency is ScheduleFrequency.MANUAL
    assert Schedule().to_dict()["frequency"] == "manual"
