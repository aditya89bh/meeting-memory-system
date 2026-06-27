"""Persistent storage for meeting memory.

Phase 3 turns extracted memories into durable organizational memory: meetings
and their memories are persisted to a deterministic SQLite database so questions
like "what decisions have we made?" or "which risks keep appearing?" can be
answered later, across many meetings.

The layer is intentionally simple and dependency-free: standard-library
``sqlite3`` only, no ORM, no vector database, and no semantic search.
"""

from __future__ import annotations

from .hashing import memory_content_hash, transcript_hash
from .models import (
    MemoryQuery,
    MemoryStatus,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
)

__all__ = [
    "MemoryQuery",
    "MemoryStatus",
    "StoredEvidence",
    "StoredMeeting",
    "StoredMemory",
    "memory_content_hash",
    "transcript_hash",
]
