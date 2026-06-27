"""Memory-oriented service: querying and reading stored memory records."""

from __future__ import annotations

from pathlib import Path

from ..storage import MemoryQuery, MemoryStatus, SQLiteMemoryStore, StoredMemory


class MemoryService:
    """Query and read stored memories."""

    def __init__(self, db: str | Path) -> None:
        self.db = Path(db)

    def query(self, query: MemoryQuery) -> list[StoredMemory]:
        """Return memories matching a structured query."""
        with SQLiteMemoryStore(self.db) as store:
            return store.query(query)

    def list_memories(
        self,
        *,
        memory_types: frozenset[str] | None = None,
        speakers: frozenset[str] | None = None,
        meeting_ids: frozenset[str] | None = None,
        statuses: frozenset[MemoryStatus] | None = None,
        min_confidence: float | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StoredMemory]:
        """Return memories filtered by the common dimensions, with pagination."""
        query = MemoryQuery(
            memory_types=memory_types,
            speakers=speakers,
            meeting_ids=meeting_ids,
            statuses=statuses,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
        return self.query(query)

    def count(self, query: MemoryQuery | None = None) -> int:
        """Return the number of memories matching ``query`` (or all memories)."""
        with SQLiteMemoryStore(self.db) as store:
            return store.count(query)

    def get_memory(self, memory_id: str) -> StoredMemory:
        """Return a single memory by id (raises ``MemoryNotFoundError``)."""
        with SQLiteMemoryStore(self.db) as store:
            return store.get(memory_id)
