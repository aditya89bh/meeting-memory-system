"""Deterministic retrieval engine for organizational meeting memory.

Phase 4 searches the persistent store built in Phase 3. It plans a query into
concrete filters, retrieves matching memories with AND semantics, ranks them with
a transparent deterministic scoring model, assembles surrounding context, and
explains why each memory was returned.

No LLM APIs, embeddings, vector databases, or external search engines are used.
"""

from __future__ import annotations

from .context import ContextAssembler
from .engine import MemoryRetriever
from .explain import explain_match
from .models import (
    ContextUtterance,
    ContextWindow,
    ExplanationReason,
    RankedMemory,
    RetrievalExplanation,
    RetrievalFilter,
    RetrievalQuery,
    RetrievalResult,
    RetrievalStats,
)
from .planner import PlannerVocabulary, QueryPlanner
from .ranking import (
    DEFAULT_WEIGHTS,
    RankingWeights,
    ScoreComponents,
    score_components,
    score_memory,
)

__all__ = [
    "DEFAULT_WEIGHTS",
    "ContextAssembler",
    "ContextUtterance",
    "ContextWindow",
    "ExplanationReason",
    "MemoryRetriever",
    "PlannerVocabulary",
    "QueryPlanner",
    "RankedMemory",
    "RankingWeights",
    "RetrievalExplanation",
    "RetrievalFilter",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievalStats",
    "ScoreComponents",
    "explain_match",
    "score_components",
    "score_memory",
]
