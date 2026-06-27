"""Intelligence service: insights, metrics, recommendations, and reports."""

from __future__ import annotations

from pathlib import Path

from ..graph import SQLiteGraphStore
from ..intelligence import (
    AnalysisFilters,
    Insight,
    InsightReport,
    IntelligenceEngine,
    OrganizationalHealth,
    Recommendation,
)
from ..storage import SQLiteMemoryStore


class IntelligenceService:
    """Produce deterministic organizational intelligence from stored memory."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)
        self._engine = IntelligenceEngine()

    def report(self, filters: AnalysisFilters | None = None) -> InsightReport:
        """Build the full intelligence report (insights, metrics, recommendations)."""
        with SQLiteMemoryStore(self.db) as memory_store:
            graph_store = SQLiteGraphStore(self.db)
            try:
                return self._engine.analyze(memory_store, graph_store, filters=filters)
            finally:
                graph_store.close()

    def insights(
        self,
        filters: AnalysisFilters | None = None,
        *,
        types: frozenset[str] | None = None,
        limit: int | None = None,
    ) -> list[Insight]:
        """Return discovered insights, optionally filtered by type and limited."""
        insights = list(self.report(filters).insights)
        if types is not None:
            insights = [insight for insight in insights if insight.type.value in types]
        if limit is not None:
            insights = insights[:limit]
        return insights

    def metrics(self, filters: AnalysisFilters | None = None) -> OrganizationalHealth:
        """Return the organizational-health metrics block."""
        return self.report(filters).health

    def recommendations(
        self,
        filters: AnalysisFilters | None = None,
        *,
        limit: int | None = None,
    ) -> list[Recommendation]:
        """Return prioritised recommendations, optionally limited."""
        recommendations = list(self.report(filters).recommendations)
        if limit is not None:
            recommendations = recommendations[:limit]
        return recommendations

    def render(self, report: InsightReport, fmt: str) -> str:
        """Render a report in a supported textual format (json/markdown/text)."""
        return self._engine.render(report, fmt)
