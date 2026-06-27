"""Automation engine, job runner, and pipeline executor (Phase 7).

The automation engine threads the whole system together deterministically:

    import -> graph -> intelligence -> export

A :class:`PipelineExecutor` runs an :class:`~meeting_memory.connectors.models.AutomationJob`
step by step against a shared :class:`~meeting_memory.connectors.base.ExecutionContext`,
the :class:`JobRunner` owns store/logger lifecycle for a single run, the
:class:`AutomationEngine` is the public facade (run a job or a config file), and
:class:`JobHistory` persists run results as JSON Lines for later inspection.

Wall-clock concerns are injected (``clock``/``now``) so runs are reproducible.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ..exceptions import MeetingMemoryError
from ..graph import SQLiteGraphStore, build_graph
from ..intelligence import IntelligenceEngine
from ..storage import SQLiteMemoryStore
from .base import ConnectorManager, ExecutionContext, default_manager
from .config import load_pipeline
from .logging import LogLevel, LogSink, StructuredLogger, new_correlation_id, utc_now
from .models import (
    AutomationJob,
    AutomationResult,
    ConnectorStatus,
    ExportRequest,
    ImportRequest,
    StageResult,
    StepConfig,
)


class PipelineExecutor:
    """Run the ordered steps of an automation job against an execution context."""

    def execute(self, job: AutomationJob, context: ExecutionContext) -> list[StageResult]:
        """Execute every step, stopping at the first hard failure."""
        handlers: dict[str, Callable[[StepConfig, ExecutionContext], StageResult]] = {
            "import": self._import_step,
            "graph": self._graph_step,
            "intelligence": self._intelligence_step,
            "export": self._export_step,
        }
        stages: list[StageResult] = []
        for step in job.steps:
            handler = handlers.get(step.type)
            if handler is None:
                stages.append(
                    StageResult(
                        stage=step.type,
                        status=ConnectorStatus.FAILURE,
                        errors=(f"unknown step type {step.type!r}",),
                    )
                )
                break
            try:
                stage = handler(step, context)
            except MeetingMemoryError as exc:
                context.logger.emit(LogLevel.ERROR, f"{step.type} failed: {exc}", stage=step.type)
                stage = StageResult(
                    stage=step.type, status=ConnectorStatus.FAILURE, errors=(str(exc),)
                )
            stages.append(stage)
            if stage.status is ConnectorStatus.FAILURE:
                break
        return stages

    def _import_step(self, step: StepConfig, context: ExecutionContext) -> StageResult:
        params = step.params
        raw_sources = params.get("sources") or []
        sources = tuple(str(item) for item in raw_sources) if isinstance(raw_sources, list) else ()
        raw_types = params.get("types") or params.get("memory_types") or []
        memory_types: frozenset[str] = frozenset()
        if isinstance(raw_types, list):
            memory_types = frozenset(str(item) for item in raw_types)
        request = ImportRequest(
            source=str(params.get("source", "")),
            sources=sources,
            recursive=bool(params.get("recursive", False)),
            pattern=str(params.get("pattern", "*")),
            deduplicate=bool(params.get("deduplicate", True)),
            dry_run=context.dry_run,
            now=context.now,
            min_confidence=_as_float(params.get("min_confidence"), 0.0),
            memory_types=memory_types,
            limit=_optional_int(params.get("limit")),
        )
        result = context.manager.import_source(request, context.memory_store, logger=context.logger)
        return StageResult(
            stage="import",
            status=result.status,
            connector=result.connector,
            items=result.memories_stored,
            duration_ms=result.duration_ms,
            warnings=result.warnings,
            errors=result.errors,
            details={
                "files": result.files_processed,
                "meetings": result.meetings_imported,
                "duplicates": result.duplicates,
            },
        )

    def _graph_step(self, step: StepConfig, context: ExecutionContext) -> StageResult:
        start = context.logger.mark()
        if context.graph_store is not None:
            context.graph_store.close()
        location = ":memory:" if context.dry_run else str(context.db)
        graph_store = SQLiteGraphStore(location)
        build = build_graph(context.memory_store, graph_store)
        context.graph_store = graph_store
        duration = context.logger.elapsed(start)
        context.logger.emit(
            LogLevel.INFO,
            "graph build",
            stage="graph",
            items=build.node_total,
            duration_ms=duration,
            details={"nodes": build.node_total, "edges": build.edge_total},
        )
        return StageResult(
            stage="graph",
            status=ConnectorStatus.SUCCESS,
            items=build.node_total,
            duration_ms=duration,
            details={
                "nodes_added": build.nodes_added,
                "edges_added": build.edges_added,
                "node_total": build.node_total,
                "edge_total": build.edge_total,
            },
        )

    def _intelligence_step(self, step: StepConfig, context: ExecutionContext) -> StageResult:
        start = context.logger.mark()
        graph = SQLiteGraphStore(":memory:")
        try:
            report = IntelligenceEngine().analyze(context.memory_store, graph)
        finally:
            graph.close()
        context.artifacts["report"] = report
        duration = context.logger.elapsed(start)
        items = len(report.insights)
        context.logger.emit(
            LogLevel.INFO,
            "intelligence analysis",
            stage="intelligence",
            items=items,
            duration_ms=duration,
            details={
                "insights": items,
                "recommendations": len(report.recommendations),
            },
        )
        return StageResult(
            stage="intelligence",
            status=ConnectorStatus.SUCCESS,
            items=items,
            duration_ms=duration,
            details={
                "insights": items,
                "recommendations": len(report.recommendations),
                "overall_health": report.health.overall,
            },
        )

    def _export_step(self, step: StepConfig, context: ExecutionContext) -> StageResult:
        params = step.params
        fmt = str(params.get("format", ""))
        destination = params.get("output") or params.get("destination")
        reserved = {"format", "output", "destination"}
        request = ExportRequest(
            fmt=fmt,
            destination=str(destination) if destination else None,
            dry_run=context.dry_run,
            options={key: value for key, value in params.items() if key not in reserved},
        )
        result = context.manager.export(
            request,
            context.memory_store,
            graph_store=context.graph_store,
            logger=context.logger,
        )
        return StageResult(
            stage="export",
            status=result.status,
            connector=result.connector,
            items=result.items_exported,
            duration_ms=result.duration_ms,
            warnings=result.warnings,
            errors=result.errors,
            details={
                "format": fmt,
                "destination": result.destination,
                "bytes": result.bytes_written,
            },
        )


def _optional_int(value: object) -> int | None:
    """Coerce a config value into an optional integer."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(str(value))


def _as_float(value: object, default: float) -> float:
    """Coerce a config value into a float, falling back to ``default``."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


def _aggregate_status(stages: list[StageResult], *, dry_run: bool) -> ConnectorStatus:
    """Combine stage statuses into one automation status."""
    if any(stage.status is ConnectorStatus.FAILURE for stage in stages):
        return ConnectorStatus.FAILURE
    if any(stage.status is ConnectorStatus.PARTIAL for stage in stages):
        return ConnectorStatus.PARTIAL
    if dry_run:
        return ConnectorStatus.DRY_RUN
    return ConnectorStatus.SUCCESS


class JobRunner:
    """Own the store, graph, and logger lifecycle for a single job run."""

    def __init__(
        self,
        *,
        manager: ConnectorManager | None = None,
        clock: Callable[[], float] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._manager = manager if manager is not None else default_manager()
        self._clock = clock
        self._now = now

    def run(
        self,
        job: AutomationJob,
        *,
        db: str | Path,
        dry_run: bool = False,
        logger: StructuredLogger | None = None,
        correlation_id: str | None = None,
    ) -> AutomationResult:
        """Execute ``job`` end to end and return a deterministic result."""
        cid = correlation_id or (logger.correlation_id if logger else new_correlation_id())
        active_logger = logger or StructuredLogger(cid, clock=self._clock, now=self._now)
        started_at = (self._now() if self._now else utc_now()).isoformat()
        start_clock = active_logger.mark()

        store = SQLiteMemoryStore(db)
        context = ExecutionContext(
            db=Path(db),
            memory_store=store,
            manager=self._manager,
            logger=active_logger,
            correlation_id=cid,
            now=started_at if self._now is not None else None,
            dry_run=dry_run,
        )
        try:
            stages = PipelineExecutor().execute(job, context)
        finally:
            if context.graph_store is not None:
                context.graph_store.close()
            store.close()

        duration = active_logger.elapsed(start_clock)
        finished_at = (self._now() if self._now else utc_now()).isoformat()
        status = _aggregate_status(stages, dry_run=dry_run)
        errors = tuple(error for stage in stages for error in stage.errors)
        result = AutomationResult(
            job=job.name,
            correlation_id=cid,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration,
            stages=tuple(stages),
            errors=errors,
            dry_run=dry_run,
        )
        active_logger.emit(
            LogLevel.ERROR if status is ConnectorStatus.FAILURE else LogLevel.INFO,
            f"job {job.name} {status.value}",
            stage="job",
            items=len(stages),
            duration_ms=duration,
            errors=len(errors),
            details={"correlation_id": cid},
        )
        return result


class JobHistory:
    """Persist automation results as JSON Lines for the ``jobs`` command."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, result: AutomationResult) -> None:
        """Append a single run result as one JSON line."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def list(self, *, limit: int | None = None) -> list[dict[str, object]]:
        """Return recorded run results (most recent ``limit``), in file order."""
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                records.append(json.loads(text))
        if limit is not None and limit >= 0:
            records = records[-limit:]
        return records


class AutomationEngine:
    """Public facade for running automation jobs and pipeline files."""

    def __init__(
        self,
        *,
        manager: ConnectorManager | None = None,
        history: JobHistory | None = None,
        log_sink: object | None = None,
        clock: Callable[[], float] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._runner = JobRunner(manager=manager, clock=clock, now=now)
        self._history = history
        self._log_sink = log_sink
        self._clock = clock
        self._now = now

    def run_job(
        self,
        job: AutomationJob,
        *,
        db: str | Path,
        dry_run: bool = False,
    ) -> AutomationResult:
        """Run a constructed job, persisting the result to history when configured."""
        cid = new_correlation_id()
        sink = self._log_sink if isinstance(self._log_sink, LogSink) else None
        logger = StructuredLogger(cid, sink=sink, clock=self._clock, now=self._now)
        result = self._runner.run(job, db=db, dry_run=dry_run, logger=logger, correlation_id=cid)
        if self._history is not None:
            self._history.record(result)
        return result

    def run_file(
        self,
        path: str | Path,
        *,
        db: str | Path,
        dry_run: bool = False,
    ) -> AutomationResult:
        """Load, validate, and run a pipeline configuration file."""
        job = load_pipeline(path)
        return self.run_job(job, db=db, dry_run=dry_run)
