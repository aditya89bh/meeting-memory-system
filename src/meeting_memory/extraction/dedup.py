"""Deduplication of extracted memories within a single meeting.

Different trigger phrases can produce the same memory (e.g. an utterance that
contains both "we decided" and "approved"), and speakers often restate the same
point. Deduplication collapses records of the **same type** whose text matches
after light normalization, keeping the highest-confidence record.

The matching is intentionally simple (normalized exact text). It adds no
heavyweight or vector dependencies.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .models import ExtractedMemory, MemoryType

_NON_WORD_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize text for duplicate comparison.

    Lowercases, removes punctuation, and collapses whitespace so that
    "We decided!" and "we decided" compare equal.
    """
    without_punct = _NON_WORD_RE.sub(" ", text.lower())
    return _WHITESPACE_RE.sub(" ", without_punct).strip()


def _key(memory: ExtractedMemory) -> tuple[MemoryType, str]:
    return (memory.memory_type, normalize_text(memory.text))


def deduplicate(memories: Sequence[ExtractedMemory]) -> list[ExtractedMemory]:
    """Remove duplicate memories, keeping the highest-confidence record per key.

    Two memories are duplicates when they share a type and have identical
    normalized text. Ties keep the earliest record. The relative order of the
    surviving records (by their position in the input) is preserved.
    """
    winners: dict[tuple[MemoryType, str], ExtractedMemory] = {}
    for memory in memories:
        key = _key(memory)
        current = winners.get(key)
        if current is None or memory.confidence > current.confidence:
            winners[key] = memory

    original_order = {id(memory): index for index, memory in enumerate(memories)}
    return sorted(winners.values(), key=lambda memory: original_order[id(memory)])
