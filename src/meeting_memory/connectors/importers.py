"""Deterministic file import connectors (Phase 7).

Every importer reuses the existing pipeline — loader/parser -> extraction ->
storage — so an imported transcript flows through exactly the same stages as the
``import`` command. Markdown notes and CSV action items are normalised into the
plain-text transcript shape the parser already understands, keeping a single
source of truth for parsing.

Connectors validate their request up front, support a no-write ``dry_run`` that
parses and counts without persisting, log structured progress, and degrade
gracefully: a malformed file becomes a failed per-file outcome rather than an
exception that aborts a whole batch.
"""

from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..exceptions import ConnectorValidationError, MeetingMemoryError
from ..extraction import ExtractionConfig, MemoryType, extract_memories
from ..models import Meeting
from ..parser import MeetingParser
from ..storage.base import MemoryStore
from ..storage.hashing import transcript_hash
from ..storage.persistence import persist_extraction
from .base import (
    IMPORT_ARCHIVE,
    IMPORT_BATCH,
    IMPORT_DIRECTORY,
    IMPORT_RECURSIVE,
    IMPORT_TEXT,
    ConnectorRegistry,
    ImportConnector,
)
from .logging import LogLevel, StructuredLogger
from .models import (
    ConnectorCapability,
    ConnectorMetadata,
    ConnectorStatus,
    ConnectorType,
    FileImportOutcome,
    ImportRequest,
    ImportResult,
)

CONNECTOR_VERSION = "1.0"

# File extensions the framework can ingest, mapped to a canonical parser format.
_EXTENSION_FORMATS: dict[str, str] = {
    "txt": "txt",
    "json": "json",
    "md": "markdown",
    "markdown": "markdown",
    "csv": "csv",
}

_MAX_SPEAKER_WORDS = 6
_MAX_SPEAKER_CHARS = 50
_LIST_MARKER_RE = re.compile(r"^[-*+]\s+(.*)$")


@dataclass(frozen=True)
class _FileSource:
    """A single resolved file to ingest, with its parser format and label."""

    path: Path
    fmt: str
    label: str


def _created_at(now: str | None) -> datetime:
    """Resolve the creation timestamp, defaulting to the current UTC time."""
    if now is None:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(now)


def _extraction_config(request: ImportRequest) -> ExtractionConfig:
    """Build an :class:`ExtractionConfig` from the request, validating types."""
    enabled: frozenset[MemoryType] | None
    if request.memory_types:
        try:
            enabled = frozenset(MemoryType(value) for value in request.memory_types)
        except ValueError as exc:
            raise ConnectorValidationError(f"unknown memory type: {exc}") from exc
    else:
        enabled = None
    return ExtractionConfig(
        enabled_types=enabled,
        min_confidence=request.min_confidence,
        deduplicate=request.deduplicate,
    )


def _looks_like_turn(line: str) -> bool:
    """Heuristic: does ``line`` read like a ``Speaker: text`` transcript turn?"""
    head, sep, _ = line.partition(":")
    head = head.strip()
    if not sep or not head:
        return False
    return len(head) <= _MAX_SPEAKER_CHARS and len(head.split()) <= _MAX_SPEAKER_WORDS


def markdown_to_transcript(text: str) -> str:
    """Normalise markdown meeting notes into a plain-text transcript.

    Leading ``---`` front matter is preserved (the text parser consumes it).
    Bullet/emphasis markers are stripped, headings and non-turn prose are
    dropped, so only ``Speaker: text`` turns survive — exactly what the parser
    expects.
    """
    lines = text.split("\n")
    out: list[str] = []
    start = 0
    if lines and lines[0].strip() == "---":
        out.append("---")
        for index in range(1, len(lines)):
            out.append(lines[index])
            if lines[index].strip() == "---":
                start = index + 1
                break

    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        if stripped.startswith("#"):
            continue
        match = _LIST_MARKER_RE.match(stripped)
        content = match.group(1) if match else stripped
        content = content.replace("**", "").replace("__", "").strip()
        if _looks_like_turn(content):
            out.append(content)
    return "\n".join(out)


def _first_column(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
    """Return the first non-empty value among ``keys`` in a CSV ``row``."""
    lowered = {key.lower().strip(): value for key, value in row.items() if key}
    for key in keys:
        value = lowered.get(key)
        if value is not None and value.strip():
            return value.strip()
    return None


def csv_to_transcript(text: str) -> str:
    """Normalise a CSV of action items into a plain-text transcript.

    Recognised owner columns: speaker/owner/name/assignee. Recognised content
    columns: text/action/item/task/note/description/summary. Rows missing either
    are skipped.
    """
    reader = csv.DictReader(io.StringIO(text))
    lines: list[str] = []
    for row in reader:
        speaker = _first_column(row, ("speaker", "owner", "name", "assignee"))
        body = _first_column(
            row, ("text", "action", "item", "task", "note", "description", "summary")
        )
        if speaker is None or body is None:
            continue
        lines.append(f"{speaker}: {body}")
    return "\n".join(lines)


def _parse_meeting(raw_text: str, source: _FileSource) -> Meeting:
    """Parse raw file contents into a :class:`Meeting` for its format."""
    parser = MeetingParser()
    if source.fmt == "json":
        return parser.parse_json(json.loads(raw_text), source_path=source.label)
    if source.fmt == "markdown":
        return parser.parse_text(markdown_to_transcript(raw_text), source_path=source.label)
    if source.fmt == "csv":
        return parser.parse_text(csv_to_transcript(raw_text), source_path=source.label)
    return parser.parse_text(raw_text, source_path=source.label)


def _process_file(
    source: _FileSource,
    *,
    store: MemoryStore | None,
    config: ExtractionConfig,
    created_at: datetime,
    deduplicate: bool,
    dry_run: bool,
) -> FileImportOutcome:
    """Ingest a single file, returning its outcome (never raising on bad input)."""
    try:
        raw_text = source.path.read_text(encoding="utf-8")
    except OSError as exc:
        return FileImportOutcome(path=source.label, status=ConnectorStatus.FAILURE, error=str(exc))

    digest = transcript_hash(raw_text)
    if store is not None:
        existing = store.find_meeting_by_hash(digest)
        if existing is not None:
            return FileImportOutcome(
                path=source.label,
                status=ConnectorStatus.SKIPPED,
                meeting_id=existing.meeting_id,
                duplicate=True,
            )

    try:
        meeting = _parse_meeting(raw_text, source)
        result = extract_memories(meeting, config=config, now=created_at)
    except (MeetingMemoryError, json.JSONDecodeError) as exc:
        return FileImportOutcome(path=source.label, status=ConnectorStatus.FAILURE, error=str(exc))

    if dry_run or store is None:
        return FileImportOutcome(
            path=source.label,
            status=ConnectorStatus.DRY_RUN,
            meeting_id=result.meeting_id,
            stored=result.total,
        )

    persisted = persist_extraction(
        store,
        meeting,
        result,
        transcript_hash=digest,
        created_at=created_at,
        deduplicate=deduplicate,
    )
    return FileImportOutcome(
        path=source.label,
        status=ConnectorStatus.SUCCESS,
        meeting_id=persisted.meeting.meeting_id,
        stored=persisted.stored_count,
    )


def _aggregate_status(outcomes: list[FileImportOutcome], *, dry_run: bool) -> ConnectorStatus:
    """Combine per-file outcomes into a single connector status."""
    if not outcomes:
        return ConnectorStatus.SUCCESS
    failures = [o for o in outcomes if o.status is ConnectorStatus.FAILURE]
    non_failures = [o for o in outcomes if o.status is not ConnectorStatus.FAILURE]
    if failures and non_failures:
        return ConnectorStatus.PARTIAL
    if failures:
        return ConnectorStatus.FAILURE
    return ConnectorStatus.DRY_RUN if dry_run else ConnectorStatus.SUCCESS


def _run_import(
    *,
    name: str,
    sources: list[_FileSource],
    request: ImportRequest,
    store: MemoryStore | None,
    dry_run: bool,
    logger: StructuredLogger | None,
) -> ImportResult:
    """Ingest a resolved list of files and assemble an :class:`ImportResult`."""
    start = logger.mark() if logger is not None else 0.0
    config = _extraction_config(request)
    created_at = _created_at(request.now)

    outcomes: list[FileImportOutcome] = []
    errors: list[str] = []
    warnings: list[str] = []
    if not sources:
        warnings.append("no matching files to import")

    for source in sources:
        outcome = _process_file(
            source,
            store=store,
            config=config,
            created_at=created_at,
            deduplicate=request.deduplicate,
            dry_run=dry_run,
        )
        outcomes.append(outcome)
        if outcome.error is not None:
            errors.append(f"{outcome.path}: {outcome.error}")

    imported = sum(1 for o in outcomes if o.status is ConnectorStatus.SUCCESS)
    previewed = sum(1 for o in outcomes if o.status is ConnectorStatus.DRY_RUN)
    status = _aggregate_status(outcomes, dry_run=dry_run)
    duration = logger.elapsed(start) if logger is not None else 0.0
    result = ImportResult(
        connector=name,
        status=status,
        files_processed=len(outcomes),
        meetings_imported=previewed if dry_run else imported,
        memories_stored=sum(o.stored for o in outcomes),
        duplicates=sum(1 for o in outcomes if o.duplicate),
        outcomes=tuple(outcomes),
        warnings=tuple(warnings),
        errors=tuple(errors),
        duration_ms=duration,
        correlation_id=logger.correlation_id if logger is not None else None,
        dry_run=dry_run,
    )
    if logger is not None:
        logger.emit(
            LogLevel.ERROR if status is ConnectorStatus.FAILURE else LogLevel.INFO,
            f"import {name} {status.value}",
            stage="import",
            connector=name,
            items=result.memories_stored,
            duration_ms=duration,
            warnings=len(warnings),
            errors=len(errors),
            details={"files": result.files_processed, "meetings": result.meetings_imported},
        )
    return result


def _supported_extension(path: Path) -> bool:
    """Whether ``path`` has a supported transcript extension."""
    return path.suffix.lower().lstrip(".") in _EXTENSION_FORMATS


def _format_for(path: Path) -> str:
    """Return the canonical parser format for a path's extension."""
    return _EXTENSION_FORMATS[path.suffix.lower().lstrip(".")]


class _SingleFileImportConnector(ImportConnector):
    """Shared base for single-format file importers (text/json/markdown/csv)."""

    name_id: str
    formats: tuple[str, ...]
    canonical: str
    summary: str

    def metadata(self) -> ConnectorMetadata:
        """Describe this single-file import connector."""
        return ConnectorMetadata(
            name=self.name_id,
            version=CONNECTOR_VERSION,
            connector_type=ConnectorType.IMPORT,
            description=self.summary,
            capabilities=frozenset({ConnectorCapability.VALIDATION, ConnectorCapability.DRY_RUN}),
            formats=self.formats,
        )

    def validate(self, request: ImportRequest) -> list[str]:
        """Validate the source path and its extension."""
        problems: list[str] = []
        path = Path(request.source)
        if not path.exists():
            problems.append(f"source does not exist: {path}")
        elif not path.is_file():
            problems.append(f"source is not a file: {path}")
        elif path.suffix.lower().lstrip(".") not in self.formats:
            problems.append(
                f"{path} is not a {self.name_id} file (expected: {', '.join(self.formats)})"
            )
        return problems

    def _source(self, request: ImportRequest) -> _FileSource:
        path = Path(request.source)
        return _FileSource(path=path, fmt=self.canonical, label=str(path))

    def execute(
        self,
        request: ImportRequest,
        store: MemoryStore,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Import the single source file into ``store``."""
        return _run_import(
            name=self.name_id,
            sources=[self._source(request)],
            request=request,
            store=store,
            dry_run=False,
            logger=logger,
        )

    def dry_run(
        self,
        request: ImportRequest,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Preview the single-file import without writing."""
        return _run_import(
            name=self.name_id,
            sources=[self._source(request)],
            request=request,
            store=None,
            dry_run=True,
            logger=logger,
        )


class TextImportConnector(_SingleFileImportConnector):
    """Import a plain-text transcript."""

    name_id = IMPORT_TEXT
    formats = ("txt",)
    canonical = "txt"
    summary = "Import a plain-text transcript."


class JsonImportConnector(_SingleFileImportConnector):
    """Import a structured JSON transcript."""

    name_id = "json"
    formats = ("json",)
    canonical = "json"
    summary = "Import a structured JSON transcript."


class MarkdownImportConnector(_SingleFileImportConnector):
    """Import markdown meeting notes."""

    name_id = "markdown"
    formats = ("md", "markdown")
    canonical = "markdown"
    summary = "Import markdown meeting notes."


class CsvImportConnector(_SingleFileImportConnector):
    """Import a CSV of action items."""

    name_id = "csv"
    formats = ("csv",)
    canonical = "csv"
    summary = "Import a CSV of action items."


class DirectoryImportConnector(ImportConnector):
    """Import every supported transcript in a directory (non-recursive)."""

    name_id = IMPORT_DIRECTORY
    recursive = False
    summary = "Import every supported transcript in a directory."

    def metadata(self) -> ConnectorMetadata:
        """Describe the directory import connector."""
        capabilities = {
            ConnectorCapability.VALIDATION,
            ConnectorCapability.DRY_RUN,
            ConnectorCapability.DIRECTORY,
        }
        if self.recursive:
            capabilities.add(ConnectorCapability.RECURSIVE)
        return ConnectorMetadata(
            name=self.name_id,
            version=CONNECTOR_VERSION,
            connector_type=ConnectorType.IMPORT,
            description=self.summary,
            capabilities=frozenset(capabilities),
            formats=tuple(sorted(_EXTENSION_FORMATS)),
        )

    def validate(self, request: ImportRequest) -> list[str]:
        """Validate that the source is an existing directory."""
        problems: list[str] = []
        path = Path(request.source)
        if not path.exists():
            problems.append(f"source does not exist: {path}")
        elif not path.is_dir():
            problems.append(f"source is not a directory: {path}")
        return problems

    def _gather(self, request: ImportRequest) -> list[_FileSource]:
        root = Path(request.source)
        recursive = self.recursive or request.recursive
        matches = root.rglob(request.pattern) if recursive else root.glob(request.pattern)
        files = sorted(p for p in matches if p.is_file() and _supported_extension(p))
        if request.limit is not None:
            files = files[: request.limit]
        return [_FileSource(path=p, fmt=_format_for(p), label=str(p)) for p in files]

    def execute(
        self,
        request: ImportRequest,
        store: MemoryStore,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Import all matching files in the directory into ``store``."""
        return _run_import(
            name=self.name_id,
            sources=self._gather(request),
            request=request,
            store=store,
            dry_run=False,
            logger=logger,
        )

    def dry_run(
        self,
        request: ImportRequest,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Preview a directory import without writing."""
        return _run_import(
            name=self.name_id,
            sources=self._gather(request),
            request=request,
            store=None,
            dry_run=True,
            logger=logger,
        )


class RecursiveDirectoryImportConnector(DirectoryImportConnector):
    """Import every supported transcript in a directory tree, recursively."""

    name_id = IMPORT_RECURSIVE
    recursive = True
    summary = "Recursively import every supported transcript in a directory tree."


class BatchImportConnector(ImportConnector):
    """Import an explicit, ordered list of transcript files."""

    name_id = IMPORT_BATCH
    summary = "Import an explicit list of transcript files."

    def metadata(self) -> ConnectorMetadata:
        """Describe the batch import connector."""
        return ConnectorMetadata(
            name=self.name_id,
            version=CONNECTOR_VERSION,
            connector_type=ConnectorType.IMPORT,
            description=self.summary,
            capabilities=frozenset(
                {
                    ConnectorCapability.VALIDATION,
                    ConnectorCapability.DRY_RUN,
                    ConnectorCapability.BATCH,
                }
            ),
            formats=tuple(sorted(_EXTENSION_FORMATS)),
        )

    def validate(self, request: ImportRequest) -> list[str]:
        """Validate that an explicit, existing list of files was supplied."""
        problems: list[str] = []
        if not request.sources:
            problems.append("batch import requires a non-empty 'sources' list")
        for raw in request.sources:
            path = Path(raw)
            if not path.exists():
                problems.append(f"source does not exist: {path}")
            elif not path.is_file():
                problems.append(f"source is not a file: {path}")
            elif not _supported_extension(path):
                problems.append(f"unsupported file: {path}")
        return problems

    def _gather(self, request: ImportRequest) -> list[_FileSource]:
        sources: list[_FileSource] = []
        for raw in request.sources:
            path = Path(raw)
            if _supported_extension(path):
                sources.append(_FileSource(path=path, fmt=_format_for(path), label=str(path)))
        if request.limit is not None:
            sources = sources[: request.limit]
        return sources

    def execute(
        self,
        request: ImportRequest,
        store: MemoryStore,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Import the explicit list of files into ``store``."""
        return _run_import(
            name=self.name_id,
            sources=self._gather(request),
            request=request,
            store=store,
            dry_run=False,
            logger=logger,
        )

    def dry_run(
        self,
        request: ImportRequest,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Preview a batch import without writing."""
        return _run_import(
            name=self.name_id,
            sources=self._gather(request),
            request=request,
            store=None,
            dry_run=True,
            logger=logger,
        )


class ArchiveImportConnector(ImportConnector):
    """Import every supported transcript contained in a ``.zip`` archive."""

    name_id = IMPORT_ARCHIVE
    summary = "Import every supported transcript inside a zip archive."

    def metadata(self) -> ConnectorMetadata:
        """Describe the archive import connector."""
        return ConnectorMetadata(
            name=self.name_id,
            version=CONNECTOR_VERSION,
            connector_type=ConnectorType.IMPORT,
            description=self.summary,
            capabilities=frozenset(
                {
                    ConnectorCapability.VALIDATION,
                    ConnectorCapability.DRY_RUN,
                    ConnectorCapability.ARCHIVE,
                }
            ),
            formats=("zip",),
        )

    def validate(self, request: ImportRequest) -> list[str]:
        """Validate that the source is a readable zip archive."""
        problems: list[str] = []
        path = Path(request.source)
        if not path.exists():
            problems.append(f"source does not exist: {path}")
        elif not path.is_file():
            problems.append(f"source is not a file: {path}")
        elif not zipfile.is_zipfile(path):
            problems.append(f"source is not a zip archive: {path}")
        return problems

    def _run(
        self,
        request: ImportRequest,
        store: MemoryStore | None,
        *,
        dry_run: bool,
        logger: StructuredLogger | None,
    ) -> ImportResult:
        archive = Path(request.source)
        with tempfile.TemporaryDirectory(prefix="mm-archive-") as tmp:
            tmp_dir = Path(tmp)
            sources: list[_FileSource] = []
            with zipfile.ZipFile(archive) as zf:
                members = sorted(
                    info.filename
                    for info in zf.infolist()
                    if not info.is_dir() and _supported_extension(Path(info.filename))
                )
                for member in members:
                    extracted = zf.extract(member, tmp_dir)
                    sources.append(
                        _FileSource(
                            path=Path(extracted),
                            fmt=_format_for(Path(member)),
                            label=f"{archive.name}:{member}",
                        )
                    )
            if request.limit is not None:
                sources = sources[: request.limit]
            return _run_import(
                name=self.name_id,
                sources=sources,
                request=request,
                store=store,
                dry_run=dry_run,
                logger=logger,
            )

    def execute(
        self,
        request: ImportRequest,
        store: MemoryStore,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Import all supported transcripts inside the archive into ``store``."""
        return self._run(request, store, dry_run=False, logger=logger)

    def dry_run(
        self,
        request: ImportRequest,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Preview an archive import without writing."""
        return self._run(request, None, dry_run=True, logger=logger)


def register_all(registry: ConnectorRegistry) -> None:
    """Register every built-in import connector with ``registry``."""
    registry.register_import(TextImportConnector(), formats=("txt",))
    registry.register_import(JsonImportConnector(), formats=("json",))
    registry.register_import(MarkdownImportConnector(), formats=("md", "markdown"))
    registry.register_import(CsvImportConnector(), formats=("csv",))
    registry.register_import(DirectoryImportConnector())
    registry.register_import(RecursiveDirectoryImportConnector())
    registry.register_import(BatchImportConnector())
    registry.register_import(ArchiveImportConnector())
