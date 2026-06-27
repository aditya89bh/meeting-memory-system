"""Automation service: run pipelines and read job history and logs."""

from __future__ import annotations

import time
from pathlib import Path

from ..connectors import (
    AutomationEngine,
    AutomationJob,
    AutomationResult,
    JobHistory,
    JsonlFileLogSink,
    build_job,
    load_pipeline,
    read_logs,
    utc_now,
    validate_job,
)
from ..exceptions import PipelineConfigError


def jobs_path(db: str | Path) -> Path:
    """Return the job-history JSON Lines path beside a database."""
    path = Path(db)
    return path.with_name(path.name + ".jobs.jsonl")


def logs_path(db: str | Path) -> Path:
    """Return the structured-log JSON Lines path beside a database."""
    path = Path(db)
    return path.with_name(path.name + ".logs.jsonl")


class AutomationService:
    """Run declarative pipelines and inspect their history and logs."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    def _engine(self) -> AutomationEngine:
        return AutomationEngine(
            history=JobHistory(jobs_path(self.db)),
            log_sink=JsonlFileLogSink(logs_path(self.db)),
            clock=time.monotonic,
            now=utc_now,
        )

    def run_file(self, config: str | Path, *, dry_run: bool = False) -> AutomationResult:
        """Load, validate, and run a pipeline configuration file."""
        return self._engine().run_file(config, db=self.db, dry_run=dry_run)

    def run_job(self, job: AutomationJob, *, dry_run: bool = False) -> AutomationResult:
        """Run an already-built automation job."""
        return self._engine().run_job(job, db=self.db, dry_run=dry_run)

    def run_config(self, data: dict[str, object], *, dry_run: bool = False) -> AutomationResult:
        """Build, validate, and run a pipeline from parsed configuration data."""
        job = build_job(data)
        problems = validate_job(job)
        if problems:
            raise PipelineConfigError("invalid pipeline configuration: " + "; ".join(problems))
        return self.run_job(job, dry_run=dry_run)

    def load(self, config: str | Path) -> AutomationJob:
        """Load and validate a pipeline file without running it."""
        return load_pipeline(config)

    def jobs(self, *, limit: int | None = None) -> list[dict[str, object]]:
        """Return recorded automation runs (most recent ``limit``)."""
        return JobHistory(jobs_path(self.db)).list(limit=limit)

    def logs(
        self,
        *,
        correlation_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Return structured logs recorded beside the database."""
        return read_logs(logs_path(self.db), correlation_id=correlation_id, limit=limit)
