"""Rule-based extractors for meeting memory primitives.

Each extractor inspects a single utterance and yields zero or one memory of its
type. :func:`default_extractors` returns one instance of every extractor; the
pipeline uses it to build the active registry.
"""

from __future__ import annotations

from .base import ExtractionContext, Extractor, PhraseExtractor, PhraseRule, make_memory_id
from .commitment import CommitmentExtractor
from .decision import DecisionExtractor

__all__ = [
    "CommitmentExtractor",
    "DecisionExtractor",
    "ExtractionContext",
    "Extractor",
    "PhraseExtractor",
    "PhraseRule",
    "default_extractors",
    "make_memory_id",
]


def default_extractors() -> list[Extractor]:
    """Return one instance of every built-in extractor, in canonical order."""
    return [
        DecisionExtractor(),
        CommitmentExtractor(),
    ]
