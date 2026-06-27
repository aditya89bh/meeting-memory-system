"""SQLite-backed implementation of :class:`MemoryStore`.

Uses only the standard-library :mod:`sqlite3` module (no ORM). Foreign keys are
enforced, the schema is created and upgraded via deterministic migrations, and
all reads return rows in a stable order so results are reproducible.
"""

from __future__ import annotations

import builtins
import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from ..exceptions import (
    DuplicateMeetingError,
    MeetingNotFoundError,
    MemoryNotFoundError,
    StorageError,
)
from .base import MemoryStore
from .migrations import apply_migrations
from .models import (
    MemoryQuery,
    MemoryStatus,
    StoredEvidence,
    StoredMeeting,
    StoredMemory,
)

_ORDER_COLUMNS = {
    "created_at": "mem.created_at",
    "confidence": "mem.confidence",
    "meeting": "mem.meeting_id",
    "utterance": "mem.utterance_index",
}


class SQLiteMemoryStore(MemoryStore):
    """A durable memory store backed by a single SQLite database."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            self._path = str(Path(self._path).expanduser())
        self._connection = sqlite3.connect(self._path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        apply_migrations(self._connection)

    # -- memory CRUD -----------------------------------------------------------

    def save(self, memory: StoredMemory) -> None:
        try:
            with self._connection:
                self._insert_memory(memory)
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"could not store memory {memory.memory_id!r}: {exc}") from exc

    def save_many(self, memories: Iterable[StoredMemory]) -> int:
        stored = 0
        try:
            with self._connection:
                for memory in memories:
                    self._insert_memory(memory)
                    stored += 1
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"could not store memories: {exc}") from exc
        return stored

    def get(self, memory_id: str) -> StoredMemory:
        row = self._connection.execute(
            "SELECT * FROM memories WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            raise MemoryNotFoundError(f"no memory with id {memory_id!r}")
        return self._row_to_memory(row)

    def update(self, memory: StoredMemory) -> None:
        with self._connection:
            affected = self._connection.execute(
                """
                UPDATE memories SET
                    meeting_id = ?, memory_type = ?, speaker = ?, text = ?,
                    confidence = ?, utterance_index = ?, status = ?,
                    superseded_by = ?, content_hash = ?, created_at = ?, updated_at = ?
                WHERE memory_id = ?
                """,
                (
                    memory.meeting_id,
                    memory.memory_type,
                    memory.speaker,
                    memory.text,
                    memory.confidence,
                    memory.utterance_index,
                    memory.status.value,
                    memory.superseded_by,
                    memory.content_hash,
                    memory.created_at,
                    memory.updated_at,
                    memory.memory_id,
                ),
            )
            if affected.rowcount == 0:
                raise MemoryNotFoundError(f"no memory with id {memory.memory_id!r}")
            self._delete_children(memory.memory_id)
            self._insert_children(memory)

    def delete(self, memory_id: str) -> bool:
        with self._connection:
            self._delete_children(memory_id)
            affected = self._connection.execute(
                "DELETE FROM memories WHERE memory_id = ?", (memory_id,)
            )
        return affected.rowcount > 0

    def exists(self, memory_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM memories WHERE memory_id = ?", (memory_id,)
        ).fetchone()
        return row is not None

    def list(self, *, limit: int | None = None, offset: int = 0) -> builtins.list[StoredMemory]:
        sql = "SELECT mem.* FROM memories mem ORDER BY mem.created_at ASC, mem.memory_id ASC"
        sql, params = _apply_limit(sql, [], limit, offset)
        rows = self._connection.execute(sql, params).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def query(self, query: MemoryQuery) -> builtins.list[StoredMemory]:
        join, where, params = _build_filters(query)
        order_column = _ORDER_COLUMNS.get(query.order_by)
        if order_column is None:
            raise StorageError(f"unknown order_by {query.order_by!r}")
        direction = "DESC" if query.descending else "ASC"
        sql = (
            f"SELECT mem.* FROM memories mem{join}{where} "
            f"ORDER BY {order_column} {direction}, mem.memory_id ASC"
        )
        sql, params = _apply_limit(sql, params, query.limit, query.offset)
        rows = self._connection.execute(sql, params).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def count(self, query: MemoryQuery | None = None) -> int:
        if query is None:
            row = self._connection.execute("SELECT COUNT(*) FROM memories").fetchone()
            return int(row[0])
        join, where, params = _build_filters(query)
        sql = f"SELECT COUNT(*) FROM memories mem{join}{where}"
        row = self._connection.execute(sql, params).fetchone()
        return int(row[0])

    # -- meeting registry ------------------------------------------------------

    def save_meeting(self, meeting: StoredMeeting) -> None:
        if self.meeting_exists(meeting.meeting_id):
            raise DuplicateMeetingError(f"meeting {meeting.meeting_id!r} already stored")
        if self.find_meeting_by_hash(meeting.transcript_hash) is not None:
            raise DuplicateMeetingError(
                f"a meeting with transcript hash {meeting.transcript_hash} already stored"
            )
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO meetings (
                        meeting_id, title, date, source, duration_seconds,
                        participants, transcript_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meeting.meeting_id,
                        meeting.title,
                        meeting.date,
                        meeting.source,
                        meeting.duration_seconds,
                        json.dumps(list(meeting.participants)),
                        meeting.transcript_hash,
                        meeting.created_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateMeetingError(
                f"could not store meeting {meeting.meeting_id!r}: {exc}"
            ) from exc

    def get_meeting(self, meeting_id: str) -> StoredMeeting:
        row = self._connection.execute(
            "SELECT * FROM meetings WHERE meeting_id = ?", (meeting_id,)
        ).fetchone()
        if row is None:
            raise MeetingNotFoundError(f"no meeting with id {meeting_id!r}")
        return _row_to_meeting(row)

    def meeting_exists(self, meeting_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM meetings WHERE meeting_id = ?", (meeting_id,)
        ).fetchone()
        return row is not None

    def find_meeting_by_hash(self, transcript_hash: str) -> StoredMeeting | None:
        row = self._connection.execute(
            "SELECT * FROM meetings WHERE transcript_hash = ?", (transcript_hash,)
        ).fetchone()
        return _row_to_meeting(row) if row is not None else None

    def list_meetings(
        self, *, limit: int | None = None, offset: int = 0
    ) -> builtins.list[StoredMeeting]:
        sql = (
            "SELECT * FROM meetings ORDER BY date IS NULL, date ASC, created_at ASC, meeting_id ASC"
        )
        sql, params = _apply_limit(sql, [], limit, offset)
        rows = self._connection.execute(sql, params).fetchall()
        return [_row_to_meeting(row) for row in rows]

    def delete_meeting(self, meeting_id: str) -> bool:
        with self._connection:
            for (memory_id,) in self._connection.execute(
                "SELECT memory_id FROM memories WHERE meeting_id = ?", (meeting_id,)
            ).fetchall():
                self._delete_children(memory_id)
            affected = self._connection.execute(
                "DELETE FROM meetings WHERE meeting_id = ?", (meeting_id,)
            )
        return affected.rowcount > 0

    def close(self) -> None:
        self._connection.close()

    # -- internal helpers ------------------------------------------------------

    def _insert_memory(self, memory: StoredMemory) -> None:
        self._connection.execute(
            """
            INSERT INTO memories (
                memory_id, meeting_id, memory_type, speaker, text, confidence,
                utterance_index, status, superseded_by, content_hash,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory.memory_id,
                memory.meeting_id,
                memory.memory_type,
                memory.speaker,
                memory.text,
                memory.confidence,
                memory.utterance_index,
                memory.status.value,
                memory.superseded_by,
                memory.content_hash,
                memory.created_at,
                memory.updated_at,
            ),
        )
        self._insert_children(memory)

    def _insert_children(self, memory: StoredMemory) -> None:
        for span in memory.evidence:
            self._connection.execute(
                """
                INSERT INTO evidence (memory_id, utterance_index, start, end, text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (memory.memory_id, span.utterance_index, span.start, span.end, span.text),
            )
        for key in sorted(memory.metadata):
            self._connection.execute(
                """
                INSERT INTO metadata (owner_type, owner_id, key, value)
                VALUES ('memory', ?, ?, ?)
                """,
                (memory.memory_id, key, memory.metadata[key]),
            )

    def _delete_children(self, memory_id: str) -> None:
        self._connection.execute("DELETE FROM evidence WHERE memory_id = ?", (memory_id,))
        self._connection.execute(
            "DELETE FROM metadata WHERE owner_type = 'memory' AND owner_id = ?",
            (memory_id,),
        )

    def _row_to_memory(self, row: sqlite3.Row) -> StoredMemory:
        evidence_rows = self._connection.execute(
            """
            SELECT utterance_index, start, end, text FROM evidence
            WHERE memory_id = ? ORDER BY id ASC
            """,
            (row["memory_id"],),
        ).fetchall()
        evidence = tuple(
            StoredEvidence(
                utterance_index=item["utterance_index"],
                start=item["start"],
                end=item["end"],
                text=item["text"],
            )
            for item in evidence_rows
        )
        metadata_rows = self._connection.execute(
            """
            SELECT key, value FROM metadata
            WHERE owner_type = 'memory' AND owner_id = ? ORDER BY key ASC
            """,
            (row["memory_id"],),
        ).fetchall()
        metadata = {item["key"]: item["value"] for item in metadata_rows}
        return StoredMemory(
            memory_id=row["memory_id"],
            meeting_id=row["meeting_id"],
            memory_type=row["memory_type"],
            text=row["text"],
            confidence=row["confidence"],
            utterance_index=row["utterance_index"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=MemoryStatus(row["status"]),
            speaker=row["speaker"],
            superseded_by=row["superseded_by"],
            metadata=metadata,
            evidence=evidence,
        )


def _row_to_meeting(row: sqlite3.Row) -> StoredMeeting:
    """Map a ``meetings`` row to a :class:`StoredMeeting`."""
    participants = tuple(json.loads(row["participants"]))
    return StoredMeeting(
        meeting_id=row["meeting_id"],
        transcript_hash=row["transcript_hash"],
        created_at=row["created_at"],
        title=row["title"],
        date=row["date"],
        source=row["source"],
        duration_seconds=row["duration_seconds"],
        participants=participants,
    )


def _apply_limit(
    sql: str, params: list[object], limit: int | None, offset: int
) -> tuple[str, list[object]]:
    """Append ``LIMIT``/``OFFSET`` clauses when a limit is requested."""
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params = [*params, limit, offset]
    elif offset:
        sql += " LIMIT -1 OFFSET ?"
        params = [*params, offset]
    return sql, params


def _in_clause(column: str, values: frozenset[str]) -> tuple[str, list[object]]:
    """Build a deterministic ``column IN (...)`` fragment."""
    ordered = sorted(values)
    placeholders = ", ".join("?" for _ in ordered)
    return f"{column} IN ({placeholders})", list(ordered)


def _build_filters(query: MemoryQuery) -> tuple[str, str, list[object]]:
    """Translate a :class:`MemoryQuery` into ``(join, where, params)`` SQL."""
    clauses: list[str] = []
    params: list[object] = []

    if query.memory_types:
        clause, values = _in_clause("mem.memory_type", query.memory_types)
        clauses.append(clause)
        params.extend(values)
    if query.speakers:
        clause, values = _in_clause("mem.speaker", query.speakers)
        clauses.append(clause)
        params.extend(values)
    if query.meeting_ids:
        clause, values = _in_clause("mem.meeting_id", query.meeting_ids)
        clauses.append(clause)
        params.extend(values)
    if query.statuses:
        status_values = frozenset(status.value for status in query.statuses)
        clause, values = _in_clause("mem.status", status_values)
        clauses.append(clause)
        params.extend(values)
    if query.min_confidence is not None:
        clauses.append("mem.confidence >= ?")
        params.append(query.min_confidence)
    if query.max_confidence is not None:
        clauses.append("mem.confidence <= ?")
        params.append(query.max_confidence)

    needs_join = bool(query.date_from or query.date_to or query.on_date)
    if query.on_date:
        clauses.append("mt.date = ?")
        params.append(query.on_date)
    if query.date_from:
        clauses.append("mt.date >= ?")
        params.append(query.date_from)
    if query.date_to:
        clauses.append("mt.date <= ?")
        params.append(query.date_to)

    join = " JOIN meetings mt ON mt.meeting_id = mem.meeting_id" if needs_join else ""
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return join, where, params


__all__ = ["SQLiteMemoryStore"]
