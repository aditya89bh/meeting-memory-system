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

from .models import MemoryQuery, MemoryStatus, StoredMeeting, StoredMemory


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

    # -- meeting registry ------------------------------------------------------

    @abstractmethod
    def save_meeting(self, meeting: StoredMeeting) -> None:
        """Persist a meeting. Raises ``DuplicateMeetingError`` on a repeat."""

    @abstractmethod
    def get_meeting(self, meeting_id: str) -> StoredMeeting:
        """Return a meeting or raise ``MeetingNotFoundError``."""

    @abstractmethod
    def meeting_exists(self, meeting_id: str) -> bool:
        """Return whether a meeting with ``meeting_id`` is stored."""

    @abstractmethod
    def find_meeting_by_hash(self, transcript_hash: str) -> StoredMeeting | None:
        """Return the meeting with a matching transcript hash, if any."""

    @abstractmethod
    def list_meetings(
        self, *, limit: int | None = None, offset: int = 0
    ) -> builtins.list[StoredMeeting]:
        """Return stored meetings in deterministic order."""

    @abstractmethod
    def delete_meeting(self, meeting_id: str) -> bool:
        """Delete a meeting (cascading to its memories); return success."""

    # -- query helpers ---------------------------------------------------------
    #
    # These are thin, deterministic wrappers over ``query``. For richer
    # combinations (e.g. open commitments from one speaker within a date range),
    # build a :class:`MemoryQuery` directly, which AND-combines every filter.

    def find_by_type(
        self, *memory_types: str, limit: int | None = None
    ) -> builtins.list[StoredMemory]:
        """Return memories of any of the given types."""
        return self.query(MemoryQuery(memory_types=frozenset(memory_types), limit=limit))

    def find_by_speaker(
        self, *speakers: str, limit: int | None = None
    ) -> builtins.list[StoredMemory]:
        """Return memories spoken by any of the given speakers."""
        return self.query(MemoryQuery(speakers=frozenset(speakers), limit=limit))

    def find_by_meeting(
        self, *meeting_ids: str, limit: int | None = None
    ) -> builtins.list[StoredMemory]:
        """Return memories belonging to any of the given meetings."""
        return self.query(MemoryQuery(meeting_ids=frozenset(meeting_ids), limit=limit))

    def find_by_status(
        self, *statuses: MemoryStatus, limit: int | None = None
    ) -> builtins.list[StoredMemory]:
        """Return memories in any of the given lifecycle states."""
        return self.query(MemoryQuery(statuses=frozenset(statuses), limit=limit))

    def find_active(self, *, limit: int | None = None) -> builtins.list[StoredMemory]:
        """Return memories that are still active."""
        return self.find_by_status(MemoryStatus.ACTIVE, limit=limit)

    def find_by_confidence(
        self,
        min_confidence: float,
        max_confidence: float | None = None,
        *,
        limit: int | None = None,
    ) -> builtins.list[StoredMemory]:
        """Return memories whose confidence falls in the given range."""
        return self.query(
            MemoryQuery(
                min_confidence=min_confidence,
                max_confidence=max_confidence,
                limit=limit,
            )
        )

    def find_by_date(self, date: str, *, limit: int | None = None) -> builtins.list[StoredMemory]:
        """Return memories from meetings held on a specific date (YYYY-MM-DD)."""
        return self.query(MemoryQuery(on_date=date, limit=limit))

    def find_between_dates(
        self, start: str, end: str, *, limit: int | None = None
    ) -> builtins.list[StoredMemory]:
        """Return memories from meetings held between two dates (inclusive)."""
        return self.query(MemoryQuery(date_from=start, date_to=end, limit=limit))

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
