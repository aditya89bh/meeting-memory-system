"""Abstract connector interfaces, registry, and manager (Phase 7).

Connectors are the extension points of the framework. Every connector describes
itself (:meth:`Connector.metadata`), validates a typed request
(:meth:`validate`), advertises capabilities (:meth:`supports`), and runs either
for real (:meth:`execute`) or as a no-write preview (:meth:`dry_run`).

The :class:`ConnectorRegistry` provides deterministic discovery by name and by
format, and the :class:`ConnectorManager` resolves the right connector for a
given source path or export format and runs it. Future live connectors (Slack,
Zoom, Notion, Jira, GitHub) plug in by implementing these interfaces and
registering — no core changes required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..exceptions import UnknownConnectorError
from ..graph import GraphStore
from ..storage.base import MemoryStore
from .logging import StructuredLogger
from .models import (
    ConnectorCapability,
    ConnectorMetadata,
    ConnectorResult,
    ExportRequest,
    ExportResult,
    ImportRequest,
    ImportResult,
)

# Well-known connector names used for deterministic resolution.
IMPORT_TEXT = "text"
IMPORT_JSON = "json"
IMPORT_MARKDOWN = "markdown"
IMPORT_CSV = "csv"
IMPORT_DIRECTORY = "directory"
IMPORT_RECURSIVE = "recursive-directory"
IMPORT_BATCH = "batch"
IMPORT_ARCHIVE = "archive"


class Connector(ABC):
    """Common base for every connector."""

    @abstractmethod
    def metadata(self) -> ConnectorMetadata:
        """Return the connector's self-description."""

    @property
    def name(self) -> str:
        """The connector's registered name."""
        return self.metadata().name

    def supports(self, capability: ConnectorCapability) -> bool:
        """Return whether the connector advertises ``capability``."""
        return self.metadata().supports(capability)


class ImportConnector(Connector):
    """A connector that ingests meeting data into the memory store."""

    @abstractmethod
    def validate(self, request: ImportRequest) -> list[str]:
        """Return a list of validation problems (empty when the request is valid)."""

    @abstractmethod
    def execute(
        self,
        request: ImportRequest,
        store: MemoryStore,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Import data described by ``request`` into ``store``."""

    @abstractmethod
    def dry_run(
        self,
        request: ImportRequest,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Preview an import without writing to any persistent store."""


class ExportConnector(Connector):
    """A connector that exports organizational data to a destination."""

    @abstractmethod
    def validate(self, request: ExportRequest) -> list[str]:
        """Return a list of validation problems (empty when the request is valid)."""

    @abstractmethod
    def execute(
        self,
        request: ExportRequest,
        store: MemoryStore,
        *,
        graph_store: GraphStore | None = None,
        logger: StructuredLogger | None = None,
    ) -> ExportResult:
        """Export data to the destination described by ``request``."""

    @abstractmethod
    def dry_run(
        self,
        request: ExportRequest,
        store: MemoryStore,
        *,
        graph_store: GraphStore | None = None,
        logger: StructuredLogger | None = None,
    ) -> ExportResult:
        """Render an export without writing to the destination."""


@dataclass
class ExecutionContext:
    """Mutable shared state threaded through an automation pipeline.

    Unlike the immutable models, this is deliberately a mutable runtime carrier:
    stages read upstream artifacts and publish their own (for example the graph
    stage populates ``graph_store`` for the intelligence and export stages).
    """

    db: Path
    memory_store: MemoryStore
    manager: ConnectorManager
    logger: StructuredLogger
    correlation_id: str
    graph_store: GraphStore | None = None
    now: str | None = None
    dry_run: bool = False
    artifacts: dict[str, object] = field(default_factory=dict)


class AutomationConnector(Connector):
    """A connector that contributes a custom step to an automation pipeline."""

    @abstractmethod
    def run(self, context: ExecutionContext) -> ConnectorResult:
        """Execute the step against the shared execution ``context``."""


class ConnectorRegistry:
    """Deterministic registry of import, export, and automation connectors."""

    def __init__(self) -> None:
        self._imports: dict[str, ImportConnector] = {}
        self._exports: dict[str, ExportConnector] = {}
        self._automation: dict[str, AutomationConnector] = {}
        self._import_by_format: dict[str, str] = {}
        self._export_by_format: dict[str, str] = {}

    def register_import(self, connector: ImportConnector, *, formats: tuple[str, ...] = ()) -> None:
        """Register an import connector, optionally bound to file extensions."""
        self._imports[connector.name] = connector
        for fmt in formats:
            self._import_by_format[fmt.lower().lstrip(".")] = connector.name

    def register_export(self, connector: ExportConnector) -> None:
        """Register an export connector, bound to the formats in its metadata."""
        self._exports[connector.name] = connector
        for fmt in connector.metadata().formats:
            self._export_by_format[fmt.lower()] = connector.name

    def register_automation(self, connector: AutomationConnector) -> None:
        """Register a custom automation-step connector."""
        self._automation[connector.name] = connector

    def get_import(self, name: str) -> ImportConnector:
        """Return the import connector registered under ``name``."""
        try:
            return self._imports[name]
        except KeyError as exc:
            raise UnknownConnectorError(f"no import connector named {name!r}") from exc

    def get_export(self, name: str) -> ExportConnector:
        """Return the export connector registered under ``name``."""
        try:
            return self._exports[name]
        except KeyError as exc:
            raise UnknownConnectorError(f"no export connector named {name!r}") from exc

    def get_automation(self, name: str) -> AutomationConnector:
        """Return the automation connector registered under ``name``."""
        try:
            return self._automation[name]
        except KeyError as exc:
            raise UnknownConnectorError(f"no automation connector named {name!r}") from exc

    def export_for_format(self, fmt: str) -> ExportConnector:
        """Return the export connector bound to ``fmt``."""
        name = self._export_by_format.get(fmt.lower())
        if name is None:
            choices = ", ".join(sorted(self._export_by_format))
            raise UnknownConnectorError(
                f"no export connector for format {fmt!r}; choose from: {choices}"
            )
        return self._exports[name]

    def import_for_path(self, path: str | Path, *, recursive: bool = False) -> ImportConnector:
        """Resolve the right import connector for ``path`` (file, dir, or archive)."""
        target = Path(path)
        if target.is_dir():
            name = IMPORT_RECURSIVE if recursive else IMPORT_DIRECTORY
            return self.get_import(name)
        extension = target.suffix.lower().lstrip(".")
        if extension == "zip":
            return self.get_import(IMPORT_ARCHIVE)
        resolved = self._import_by_format.get(extension)
        if resolved is None:
            choices = ", ".join(sorted(self._import_by_format))
            raise UnknownConnectorError(
                f"no import connector for {target} (format {extension!r}); "
                f"supported formats: {choices}"
            )
        return self._imports[resolved]

    def list_imports(self) -> list[ImportConnector]:
        """Return import connectors sorted by name."""
        return [self._imports[name] for name in sorted(self._imports)]

    def list_exports(self) -> list[ExportConnector]:
        """Return export connectors sorted by name."""
        return [self._exports[name] for name in sorted(self._exports)]

    def list_automation(self) -> list[AutomationConnector]:
        """Return automation connectors sorted by name."""
        return [self._automation[name] for name in sorted(self._automation)]

    def import_formats(self) -> tuple[str, ...]:
        """Return the registered import file extensions, sorted."""
        return tuple(sorted(self._import_by_format))

    def export_formats(self) -> tuple[str, ...]:
        """Return the registered export formats, sorted."""
        return tuple(sorted(self._export_by_format))


class ConnectorManager:
    """High-level facade that resolves and runs connectors for a registry."""

    def __init__(self, registry: ConnectorRegistry) -> None:
        self.registry = registry

    def import_source(
        self,
        request: ImportRequest,
        store: MemoryStore,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Resolve a connector for ``request`` and import into ``store``."""
        connector = self._resolve_import(request)
        if request.dry_run:
            return connector.dry_run(request, logger=logger)
        return connector.execute(request, store, logger=logger)

    def dry_run_import(
        self,
        request: ImportRequest,
        *,
        logger: StructuredLogger | None = None,
    ) -> ImportResult:
        """Resolve a connector and preview the import without writing."""
        return self._resolve_import(request).dry_run(request, logger=logger)

    def export(
        self,
        request: ExportRequest,
        store: MemoryStore,
        *,
        graph_store: GraphStore | None = None,
        logger: StructuredLogger | None = None,
    ) -> ExportResult:
        """Resolve an export connector for ``request.fmt`` and run it."""
        connector = self.registry.export_for_format(request.fmt)
        if request.dry_run:
            return connector.dry_run(request, store, graph_store=graph_store, logger=logger)
        return connector.execute(request, store, graph_store=graph_store, logger=logger)

    def _resolve_import(self, request: ImportRequest) -> ImportConnector:
        if request.sources:
            return self.registry.get_import(IMPORT_BATCH)
        return self.registry.import_for_path(request.source, recursive=request.recursive)
