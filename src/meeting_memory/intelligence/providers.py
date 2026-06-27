"""Extension interfaces for the intelligence engine (the plugin architecture).

Every analysis is a *provider* implementing one of four small interfaces. The
engine discovers the registered providers, filters them with ``supports()``, and
executes them in a deterministic (name-sorted) order. New analyses — now or in
future phases — are added simply by registering another provider; the engine
needs no changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .context import AnalysisContext
from .models import Insight, InsightCategory, InsightReport, Recommendation


@dataclass(frozen=True)
class ProviderMetadata:
    """Self-description every provider exposes via :meth:`Provider.metadata`."""

    name: str
    version: str
    category: InsightCategory
    description: str

    def to_dict(self) -> dict[str, object]:
        """Serialise the provider metadata."""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category.value,
            "description": self.description,
        }


class Provider(ABC):
    """Common base for every provider type."""

    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Return this provider's self-description."""

    def supports(self, context: AnalysisContext) -> bool:
        """Return whether this provider can run against ``context``.

        Defaults to ``True``; override to opt out (for example, when an analysis
        needs the graph and ``context.graph`` is ``None``).
        """
        return True


class InsightProvider(Provider):
    """Produces a list of :class:`Insight` objects from the context."""

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> list[Insight]:
        """Return the insights discovered in ``context``."""


class MetricProvider(Provider):
    """Produces a single immutable metrics value object from the context."""

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> object:
        """Return a metrics dataclass (with a ``to_dict`` method)."""


class RecommendationProvider(Provider):
    """Turns the context and computed insights into recommendations."""

    @abstractmethod
    def analyze(self, context: AnalysisContext, insights: list[Insight]) -> list[Recommendation]:
        """Return recommendations derived from ``context`` and ``insights``."""


class ReportProvider(Provider):
    """Renders a finished :class:`InsightReport` into a textual format."""

    @abstractmethod
    def fmt(self) -> str:
        """Return the format name this provider renders (e.g. ``"markdown"``)."""

    @abstractmethod
    def analyze(self, report: InsightReport) -> str:
        """Render ``report`` to a string in this provider's format."""


__all__ = [
    "InsightProvider",
    "MetricProvider",
    "Provider",
    "ProviderMetadata",
    "RecommendationProvider",
    "ReportProvider",
]
