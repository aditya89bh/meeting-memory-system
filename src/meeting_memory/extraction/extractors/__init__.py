"""Rule-based extractors for meeting memory primitives.

Each extractor inspects a single utterance and yields zero or one memory of its
type. :func:`default_extractors` returns one instance of every extractor; the
pipeline uses it to build the active registry.
"""

from __future__ import annotations

from .assumption import AssumptionExtractor
from .base import ExtractionContext, Extractor, PhraseExtractor, PhraseRule, make_memory_id
from .commitment import CommitmentExtractor
from .decision import DecisionExtractor
from .fact import FactExtractor
from .open_loop import OpenLoopExtractor
from .question import QuestionExtractor
from .risk import RiskExtractor

__all__ = [
    "AssumptionExtractor",
    "CommitmentExtractor",
    "DecisionExtractor",
    "ExtractionContext",
    "Extractor",
    "FactExtractor",
    "OpenLoopExtractor",
    "PhraseExtractor",
    "PhraseRule",
    "QuestionExtractor",
    "RiskExtractor",
    "default_extractors",
    "make_memory_id",
]


def default_extractors() -> list[Extractor]:
    """Return one instance of every built-in extractor, in canonical order."""
    return [
        DecisionExtractor(),
        CommitmentExtractor(),
        OpenLoopExtractor(),
        RiskExtractor(),
        AssumptionExtractor(),
        QuestionExtractor(),
        FactExtractor(),
    ]
