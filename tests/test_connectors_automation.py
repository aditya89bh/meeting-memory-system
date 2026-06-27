"""Tests for the automation engine, pipeline executor, runner, and history."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from connector_helpers import (
    TXT_TRANSCRIPT,
    fake_clock,
    write_transcripts,
)
from meeting_memory.connectors import (
    AutomationEngine,
    AutomationJob,
    ConnectorMetadata,
    ConnectorResult,
    ConnectorStatus,
    ConnectorType,
    ExecutionContext,
    JobHistory,
    JobRunner,
    StructuredLogger,
    build_job,
    default_manager,
)
from meeting_memory.connectors.automation import PipelineExecutor, _as_float, _optional_int
from meeting_memory.connectors.base import AutomationConnector, ConnectorRegistry
from meeting_memory.storage import SQLiteMemoryStore

FIXED = datetime(2026, 2, 16, 9, 0, tzinfo=timezone.utc)


def _engine(history: JobHistory | None = None) -> AutomationEngine:
    return AutomationEngine(history=history, clock=fake_clock(), now=lambda: FIXED)


def _full_job(source: Path, report: Path) -> AutomationJob:
    return build_job(
        {
            "name": "daily",
            "schedule": {"frequency": "daily"},
            "steps": [
                {"type": "import", "source": str(source), "recursive": True},
                {"type": "graph"},
                {"type": "intelligence"},
                {"type": "export", "format": "markdown", "output": str(report)},
            ],
        }
    )


def test_full_pipeline_runs(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    report = tmp_path / "report.md"
    history = JobHistory(tmp_path / "jobs.jsonl")
    engine = _engine(history=history)
    result = engine.run_job(_full_job(source, report), db=tmp_path / "atlas.db")
    assert result.status is ConnectorStatus.SUCCESS
    stages = [stage.stage for stage in result.stages]
    assert stages == ["import", "graph", "intelligence", "export"]
    assert report.exists()
    assert len(history.list()) == 1


def test_dry_run_pipeline(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    report = tmp_path / "report.md"
    result = _engine().run_job(_full_job(source, report), db=tmp_path / "atlas.db", dry_run=True)
    assert result.status is ConnectorStatus.DRY_RUN
    assert result.dry_run is True
    assert not report.exists()


def test_run_file(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    report = tmp_path / "report.md"
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "name: p\nsteps:\n"
        f"  - type: import\n    source: {source}\n"
        "  - type: graph\n"
        f"  - type: export\n    format: markdown\n    output: {report}\n",
        encoding="utf-8",
    )
    result = _engine().run_file(config, db=tmp_path / "atlas.db")
    assert result.status is ConnectorStatus.SUCCESS
    assert report.exists()


def test_unknown_step_fails(tmp_path: Path) -> None:
    job = build_job({"name": "x", "steps": [{"type": "bogus"}, {"type": "graph"}]})
    result = _engine().run_job(job, db=tmp_path / "x.db")
    assert result.status is ConnectorStatus.FAILURE
    assert result.errors
    assert [stage.stage for stage in result.stages] == ["bogus"]


def test_import_failure_stops_pipeline(tmp_path: Path) -> None:
    job = build_job(
        {
            "name": "x",
            "steps": [{"type": "import", "source": "missing-directory"}, {"type": "graph"}],
        }
    )
    result = _engine().run_job(job, db=tmp_path / "x.db")
    assert result.status is ConnectorStatus.FAILURE
    # The graph step never runs because the import stage failed first.
    assert [stage.stage for stage in result.stages] == ["import"]


def test_partial_pipeline(tmp_path: Path) -> None:
    source = tmp_path / "mixed"
    source.mkdir()
    (source / "good.txt").write_text(TXT_TRANSCRIPT, encoding="utf-8")
    (source / "bad.json").write_text("{broken", encoding="utf-8")
    job = build_job(
        {"name": "p", "steps": [{"type": "import", "source": str(source)}, {"type": "graph"}]}
    )
    result = _engine().run_job(job, db=tmp_path / "atlas.db")
    assert result.status is ConnectorStatus.PARTIAL
    assert [stage.stage for stage in result.stages] == ["import", "graph"]


def test_pipeline_executor_rebuilds_graph(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    # Build a context and run two graph steps to exercise the close/rebuild path.
    store = SQLiteMemoryStore(str(tmp_path / "atlas.db"))
    logger = StructuredLogger("cid", clock=fake_clock())
    context = ExecutionContext(
        db=tmp_path / "atlas.db",
        memory_store=store,
        manager=default_manager(),
        logger=logger,
        correlation_id="cid",
    )
    try:
        stages = PipelineExecutor().execute(
            build_job(
                {
                    "name": "g",
                    "steps": [
                        {"type": "import", "source": str(source)},
                        {"type": "graph"},
                        {"type": "graph"},
                    ],
                }
            ),
            context,
        )
    finally:
        if context.graph_store is not None:
            context.graph_store.close()
        store.close()
    assert [stage.stage for stage in stages] == ["import", "graph", "graph"]


def test_job_history_list(tmp_path: Path) -> None:
    history = JobHistory(tmp_path / "jobs.jsonl")
    assert history.list() == []
    source = write_transcripts(tmp_path / "data")
    engine = _engine(history=history)
    job = _full_job(source, tmp_path / "r.md")
    engine.run_job(job, db=tmp_path / "atlas.db")  # type: ignore[arg-type]
    engine.run_job(job, db=tmp_path / "atlas.db")  # type: ignore[arg-type]
    assert len(history.list()) == 2
    assert len(history.list(limit=1)) == 1


def test_job_runner_without_injected_clock(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    runner = JobRunner()
    job = build_job({"name": "p", "steps": [{"type": "import", "source": str(source)}]})
    result = runner.run(job, db=tmp_path / "atlas.db")
    assert result.status is ConnectorStatus.SUCCESS
    assert result.correlation_id


def test_coercion_helpers() -> None:
    assert _optional_int(None) is None
    assert _optional_int(3) == 3
    assert _optional_int("4") == 4
    assert _as_float(None, 0.5) == 0.5
    assert _as_float(2, 0.0) == 2.0
    assert _as_float("1.5", 0.0) == 1.5


class _NoopAutomationConnector(AutomationConnector):
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name="noop", version="1.0", connector_type=ConnectorType.AUTOMATION
        )

    def run(self, context: ExecutionContext) -> ConnectorResult:
        return ConnectorResult(connector="noop", status=ConnectorStatus.SUCCESS)


def test_automation_connector_registration(tmp_path: Path) -> None:
    registry = ConnectorRegistry()
    connector = _NoopAutomationConnector()
    registry.register_automation(connector)
    assert registry.get_automation("noop") is connector
    assert registry.list_automation() == [connector]
    source = write_transcripts(tmp_path / "data")
    store = SQLiteMemoryStore(":memory:")
    context = ExecutionContext(
        db=Path(":memory:"),
        memory_store=store,
        manager=default_manager(),
        logger=StructuredLogger("cid"),
        correlation_id="cid",
    )
    try:
        assert connector.run(context).status is ConnectorStatus.SUCCESS
    finally:
        store.close()
    assert source.exists()


def test_import_step_with_params(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    job = build_job(
        {
            "name": "p",
            "steps": [
                {
                    "type": "import",
                    "source": str(source),
                    "limit": 1,
                    "min_confidence": 0.0,
                    "types": ["decision", "risk"],
                }
            ],
        }
    )
    result = _engine().run_job(job, db=tmp_path / "atlas.db")  # type: ignore[arg-type]
    assert result.stages[0].details["files"] == 1
