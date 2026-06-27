"""Retrieval service: keyword/metadata search and timeline queries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..retrieval import (
    ContextAssembler,
    ContextWindow,
    MemoryRetriever,
    RankingWeights,
    RetrievalExplanation,
    RetrievalFilter,
    RetrievalQuery,
    RetrievalResult,
    explain_match,
    score_components,
)
from ..storage import SQLiteMemoryStore, StoredMemory


@dataclass(frozen=True)
class ExplanationResult:
    """A memory together with its match explanation and surrounding context."""

    memory: StoredMemory
    explanation: RetrievalExplanation
    context: ContextWindow

    def to_dict(self) -> dict[str, object]:
        """Serialise the explanation result into JSON-compatible primitives."""
        return {
            "memory": self.memory.to_dict(),
            "explanation": self.explanation.to_dict(),
            "context": self.context.to_dict(),
        }


class RetrievalService:
    """Run deterministic retrieval over the stored organizational memory."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        """Run a ranked retrieval query."""
        with SQLiteMemoryStore(self.db) as store:
            return MemoryRetriever(store).retrieve(query)

    def timeline(self, query: RetrievalQuery) -> RetrievalResult:
        """Return matching memories in chronological order."""
        with SQLiteMemoryStore(self.db) as store:
            return MemoryRetriever(store).timeline(query)

    def explain(self, memory_id: str, *, context_size: int = 2) -> ExplanationResult:
        """Explain why a memory exists and assemble its surrounding context."""
        with SQLiteMemoryStore(self.db) as store:
            memory = store.get(memory_id)
            meeting = store.get_meeting(memory.meeting_id)
            applied = RetrievalFilter(
                memory_types=frozenset({memory.memory_type}),
                statuses=frozenset({memory.status}),
                speakers=frozenset({memory.speaker}) if memory.speaker else frozenset(),
            )
            components = score_components(memory, meeting, applied, recency=1.0)
            explanation = explain_match(memory, meeting, applied, components, RankingWeights())
            context = ContextAssembler().assemble(memory, meeting, context_size)
        return ExplanationResult(memory=memory, explanation=explanation, context=context)
