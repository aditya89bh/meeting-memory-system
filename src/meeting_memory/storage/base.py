"""The :class:`MemoryStore` storage abstraction.

``MemoryStore`` defines the persistence contract for stored memories. Concrete
back-ends (e.g.
:class:`~meeting_memory.storage.sqlite_store.SQLiteMemoryStore`) implement the
abstract methods. Higher-level capabilities (the meeting registry, the query
helpers, and lifecycle transitions) are layered on in later modules.
"""

from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from collections.abc import Iterable
from types import TracebackType

from .models import MemoryQuery, StoredMemory


class MemoryStore(ABC):
    """Abstract, deterministic store for extracted memories."""

    @abstractmethod
    def save(self, memory: StoredMemory) -> None:
        """Persist a new memory. Raises if its id already exists."""

    @abstractmethod
    def save_many(self, memories: Iterable[StoredMemory]) -> int:
        """Persist several memories, returning how many were stored."""

    @abstractmethod
    def get(self, memory_id: str) -> StoredMemory:
        """Return the memory with ``memory_id`` or raise ``MemoryNotFoundError``."""

    @abstractmethod
    def update(self, memory: StoredMemory) -> None:
        """Replace an existing memory. Raises if it does not exist."""

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Hard-delete a memory, returning whether a row was removed."""

    @abstractmethod
    def exists(self, memory_id: str) -> bool:
        """Return whether a memory with ``memory_id`` is stored."""

    @abstractmethod
    def list(self, *, limit: int | None = None, offset: int = 0) -> builtins.list[StoredMemory]:
        """Return stored memories in deterministic order."""

    @abstractmethod
    def query(self, query: MemoryQuery) -> builtins.list[StoredMemory]:
        """Return memories matching ``query`` in deterministic order."""

    @abstractmethod
    def count(self, query: MemoryQuery | None = None) -> int:
        """Count memories, optionally restricted by ``query``."""

    @abstractmethod
    def close(self) -> None:
        """Release any underlying resources (e.g. the database connection)."""

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
