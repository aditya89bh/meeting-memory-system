"""Meeting memory extraction.

Phase 2 analyses parsed :class:`~meeting_memory.models.Meeting` objects and
extracts structured *memory primitives* -- decisions, commitments, open loops,
risks, assumptions, questions, and important facts.

The implementation is fully deterministic and rule-based; it requires no
external LLM APIs or network access.
"""

from __future__ import annotations

from .models import (
    AssumptionMemory,
    CommitmentMemory,
    DecisionMemory,
    EvidenceSpan,
    ExtractedMemory,
    ExtractionResult,
    FactMemory,
    MemoryType,
    OpenLoopMemory,
    QuestionMemory,
    RiskMemory,
)
from .pipeline import (
    ExtractionConfig,
    ExtractionPipeline,
    derive_meeting_id,
    extract_memories,
)

__all__ = [
    "AssumptionMemory",
    "CommitmentMemory",
    "DecisionMemory",
    "EvidenceSpan",
    "ExtractedMemory",
    "ExtractionConfig",
    "ExtractionPipeline",
    "ExtractionResult",
    "FactMemory",
    "MemoryType",
    "OpenLoopMemory",
    "QuestionMemory",
    "RiskMemory",
    "derive_meeting_id",
    "extract_memories",
]
