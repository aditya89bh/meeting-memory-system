"""Deterministic duplicate detection for stored memories.

Two layers guard against duplicate imports:

* **Meeting level** - the transcript hash recorded in the registry blocks
  re-importing the exact same transcript (handled by the importer).
* **Memory level** - within a meeting, two memories are treated as duplicates
  when they share a content hash (same type and normalized text) and their
  confidence scores differ by no more than a threshold. This collapses repeated
  statements while still allowing the *same* point to recur across *different*
  meetings (so "which risks keep appearing?" stays answerable).
"""

from __future__ import annotations

from .base import MemoryStore
from .models import MemoryQuery, StoredMemory


def is_duplicate(left: StoredMemory, right: StoredMemory, *, threshold: float) -> bool:
    """Return whether two memories are duplicates within ``threshold``."""
    return (
        left.content_hash == right.content_hash
        and abs(left.confidence - right.confidence) <= threshold
    )


def filter_duplicates(
    store: MemoryStore,
    meeting_id: str,
    candidates: tuple[StoredMemory, ...],
    *,
    threshold: float,
) -> tuple[tuple[StoredMemory, ...], tuple[StoredMemory, ...]]:
    """Split candidates into ``(to_store, skipped)`` by duplicate detection.

    A candidate is skipped when it duplicates either an already-stored memory in
    the same meeting or an earlier candidate in this batch.
    """
    existing = list(store.query(MemoryQuery(meeting_ids=frozenset({meeting_id}))))
    to_store: list[StoredMemory] = []
    skipped: list[StoredMemory] = []
    for candidate in candidates:
        if any(is_duplicate(candidate, other, threshold=threshold) for other in existing):
            skipped.append(candidate)
            continue
        existing.append(candidate)
        to_store.append(candidate)
    return tuple(to_store), tuple(skipped)
