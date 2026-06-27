"""Validation of extracted memory records.

Every extracted memory must be internally consistent before it is returned to a
caller: it needs an id, a recognised type, a bounded confidence, non-empty text,
a meeting id, and evidence that points at a real utterance. The strict
:func:`validate_memory` raises on the first problem, while :func:`partition_valid`
is non-raising and is used by the pipeline to drop bad records and surface
warnings instead of failing the whole extraction.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..exceptions import ExtractionValidationError
from .models import ExtractedMemory, MemoryType


def check_memory(memory: ExtractedMemory, *, utterance_count: int) -> str | None:
    """Return a human-readable problem description, or ``None`` if valid."""
    if not memory.memory_id:
        return "memory is missing an id"
    if not isinstance(memory.memory_type, MemoryType):
        return f"{memory.memory_id}: invalid memory_type {memory.memory_type!r}"
    if not 0.0 <= memory.confidence <= 1.0:
        return f"{memory.memory_id}: confidence {memory.confidence} is out of range [0, 1]"
    if not memory.meeting_id:
        return f"{memory.memory_id}: missing meeting_id"
    if not memory.text.strip():
        return f"{memory.memory_id}: text is empty"
    if not 0 <= memory.utterance_index < utterance_count:
        return (
            f"{memory.memory_id}: utterance_index {memory.utterance_index} "
            f"is outside the meeting's {utterance_count} utterances"
        )
    evidence_index = memory.evidence.utterance_index
    if not 0 <= evidence_index < utterance_count:
        return (
            f"{memory.memory_id}: evidence references utterance {evidence_index}, "
            f"which is outside the meeting's {utterance_count} utterances"
        )
    return None


def validate_memory(memory: ExtractedMemory, *, utterance_count: int) -> None:
    """Validate a single memory, raising on the first problem found.

    Raises:
        ExtractionValidationError: If the memory is invalid.
    """
    problem = check_memory(memory, utterance_count=utterance_count)
    if problem is not None:
        raise ExtractionValidationError(problem)


def partition_valid(
    memories: Sequence[ExtractedMemory], *, utterance_count: int
) -> tuple[list[ExtractedMemory], list[str]]:
    """Split ``memories`` into valid records and warnings for invalid ones."""
    valid: list[ExtractedMemory] = []
    warnings: list[str] = []
    for memory in memories:
        problem = check_memory(memory, utterance_count=utterance_count)
        if problem is None:
            valid.append(memory)
        else:
            warnings.append(f"dropped invalid memory ({problem})")
    return valid, warnings
