"""Export service: render organizational data to a destination or string."""

from __future__ import annotations

from pathlib import Path

from ..connectors import ExportRequest, ExportResult, StructuredLogger, default_manager
from ..graph import SQLiteGraphStore, build_graph
from ..storage import SQLiteMemoryStore


class ExportService:
    """Export reports, memories, graphs, and summaries via connector exporters."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    def export(
        self,
        fmt: str,
        *,
        destination: str | Path | None = None,
        dry_run: bool = False,
        options: dict[str, object] | None = None,
        logger: StructuredLogger | None = None,
    ) -> ExportResult:
        """Export the stored organizational data in ``fmt`` (json/markdown/...)."""
        request = ExportRequest(
            fmt=fmt,
            destination=str(destination) if destination is not None else None,
            dry_run=dry_run,
            options=dict(options or {}),
        )
        manager = default_manager()
        with SQLiteMemoryStore(self.db) as store:
            graph_store = SQLiteGraphStore(self.db)
            try:
                build_graph(store, graph_store)
                return manager.export(request, store, graph_store=graph_store, logger=logger)
            finally:
                graph_store.close()

    @staticmethod
    def formats() -> list[str]:
        """Return the sorted set of supported export formats."""
        from ..connectors import default_registry

        return sorted(default_registry().export_formats())
