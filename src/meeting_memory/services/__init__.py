"""Shared service layer (Phase 8).

The service layer is the single orchestration surface that the CLI, the REST
API, the Python SDK, and the dashboard all call. Each service wraps the existing
parser/extraction/storage/retrieval/graph/intelligence/automation layers without
re-implementing any of their logic, so every interface stays consistent and
deterministic.

Services are constructed with a database path and open a fresh SQLite connection
per operation (mirroring the CLI), which keeps them safe to use from a
request-per-call API without sharing mutable connection state.
"""

from __future__ import annotations

from .automation import AutomationService
from .export import ExportService
from .graph import GraphService, GraphSummary, NeighborhoodResult
from .intelligence import IntelligenceService
from .meetings import MeetingService, MeetingStats
from .memories import MemoryService
from .retrieval import RetrievalService

__all__ = [
    "AutomationService",
    "ExportService",
    "GraphService",
    "GraphSummary",
    "IntelligenceService",
    "MeetingService",
    "MeetingStats",
    "MemoryService",
    "NeighborhoodResult",
    "RetrievalService",
]
