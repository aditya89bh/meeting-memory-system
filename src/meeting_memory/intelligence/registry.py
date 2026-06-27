"""Provider registry powering automatic discovery.

Domain modules (``decision``, ``commitment``, ``risk``, ``health``,
``recommendations``, ``report``) register their providers here at import time.
:func:`default_providers` imports those modules and returns the registered
providers grouped by interface, so the engine can discover and run every
analysis without hard-coding the list.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass, field
from typing import TypeVar

from .providers import (
    InsightProvider,
    MetricProvider,
    Provider,
    RecommendationProvider,
    ReportProvider,
)

_P = TypeVar("_P", bound=Provider)

# Domain modules that register providers when imported.
_PROVIDER_MODULES: tuple[str, ...] = (
    "decision",
    "commitment",
    "risk",
    "health",
    "recommendations",
    "report",
)

_INSIGHT_PROVIDERS: list[InsightProvider] = []
_METRIC_PROVIDERS: list[MetricProvider] = []
_RECOMMENDATION_PROVIDERS: list[RecommendationProvider] = []
_REPORT_PROVIDERS: list[ReportProvider] = []


def register_insight(provider: InsightProvider) -> InsightProvider:
    """Register an insight provider (idempotent by metadata name)."""
    _replace(_INSIGHT_PROVIDERS, provider)
    return provider


def register_metric(provider: MetricProvider) -> MetricProvider:
    """Register a metric provider (idempotent by metadata name)."""
    _replace(_METRIC_PROVIDERS, provider)
    return provider


def register_recommendation(provider: RecommendationProvider) -> RecommendationProvider:
    """Register a recommendation provider (idempotent by metadata name)."""
    _replace(_RECOMMENDATION_PROVIDERS, provider)
    return provider


def register_report(provider: ReportProvider) -> ReportProvider:
    """Register a report provider (idempotent by metadata name)."""
    _replace(_REPORT_PROVIDERS, provider)
    return provider


def _replace(registry: list[_P], provider: _P) -> None:
    name = provider.metadata().name
    for index, existing in enumerate(registry):
        if existing.metadata().name == name:
            registry[index] = provider
            return
    registry.append(provider)


@dataclass(frozen=True)
class ProviderSet:
    """A discovered, name-sorted bundle of providers."""

    insight: tuple[InsightProvider, ...] = ()
    metric: tuple[MetricProvider, ...] = ()
    recommendation: tuple[RecommendationProvider, ...] = ()
    report: tuple[ReportProvider, ...] = field(default=())


def _sorted(providers: list[_P]) -> tuple[_P, ...]:
    return tuple(sorted(providers, key=lambda p: p.metadata().name))


def default_providers() -> ProviderSet:
    """Import the domain modules and return all registered providers, sorted."""
    for name in _PROVIDER_MODULES:
        qualified = f"{__package__}.{name}"
        if importlib.util.find_spec(qualified) is not None:
            importlib.import_module(qualified)
    return ProviderSet(
        insight=_sorted(_INSIGHT_PROVIDERS),
        metric=_sorted(_METRIC_PROVIDERS),
        recommendation=_sorted(_RECOMMENDATION_PROVIDERS),
        report=_sorted(_REPORT_PROVIDERS),
    )


__all__ = [
    "ProviderSet",
    "default_providers",
    "register_insight",
    "register_metric",
    "register_recommendation",
    "register_report",
]
