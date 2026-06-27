"""Persistence for the organizational memory graph.

``GraphStore`` is the storage contract for nodes and edges; ``SQLiteGraphStore``
implements it against the *same* SQLite database used by the memory store (the
graph tables are added by an additive migration). Writes are idempotent: nodes
and edges have deterministic ids and are inserted with ``INSERT OR IGNORE``, so
rebuilding the graph never duplicates or overwrites existing relationships.
"""

from __future__ import annotations

import builtins
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType

from ..exceptions import NodeNotFoundError
from ..storage.migrations import apply_migrations
from .models import EntityType, GraphEdge, GraphNode, RelationshipType


class GraphStore(ABC):
    """Abstract, deterministic store for graph nodes and edges."""

    @abstractmethod
    def add_node(self, node: GraphNode) -> bool:
        """Persist a node idempotently; return whether a new row was inserted."""

    @abstractmethod
    def add_nodes(self, nodes: Iterable[GraphNode]) -> int:
        """Persist several nodes; return how many were newly inserted."""

    @abstractmethod
    def get_node(self, node_id: str) -> GraphNode:
        """Return the node with ``node_id`` or raise ``NodeNotFoundError``."""

    @abstractmethod
    def has_node(self, node_id: str) -> bool:
        """Return whether a node with ``node_id`` exists."""

    @abstractmethod
    def list_nodes(
        self,
        *,
        node_types: frozenset[EntityType] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> builtins.list[GraphNode]:
        """Return nodes in deterministic order, optionally filtered by type."""

    @abstractmethod
    def count_nodes(self) -> int:
        """Return the total number of nodes."""

    @abstractmethod
    def add_edge(self, edge: GraphEdge) -> bool:
        """Persist an edge idempotently; return whether a new row was inserted."""

    @abstractmethod
    def add_edges(self, edges: Iterable[GraphEdge]) -> int:
        """Persist several edges; return how many were newly inserted."""

    @abstractmethod
    def list_edges(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relationships: frozenset[RelationshipType] | None = None,
        limit: int | None = None,
    ) -> builtins.list[GraphEdge]:
        """Return edges in deterministic order, optionally filtered."""

    @abstractmethod
    def count_edges(self) -> int:
        """Return the total number of edges."""

    def outgoing(
        self, node_id: str, relationships: frozenset[RelationshipType] | None = None
    ) -> builtins.list[GraphEdge]:
        """Return edges leaving ``node_id``."""
        return self.list_edges(source_id=node_id, relationships=relationships)

    def incoming(
        self, node_id: str, relationships: frozenset[RelationshipType] | None = None
    ) -> builtins.list[GraphEdge]:
        """Return edges entering ``node_id``."""
        return self.list_edges(target_id=node_id, relationships=relationships)

    @abstractmethod
    def close(self) -> None:
        """Release any underlying resources."""

    def __enter__(self) -> GraphStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class SQLiteGraphStore(GraphStore):
    """A graph store backed by the shared SQLite database."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).expanduser().parent.mkdir(parents=True, exist_ok=True)
            self._path = str(Path(self._path).expanduser())
        self._connection = sqlite3.connect(self._path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        apply_migrations(self._connection)

    # -- nodes -----------------------------------------------------------------

    def add_node(self, node: GraphNode) -> bool:
        with self._connection:
            affected = self._connection.execute(
                """
                INSERT OR IGNORE INTO graph_nodes (node_id, node_type, label, ref_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (node.node_id, node.node_type.value, node.label, node.ref_id, node.created_at),
            )
            inserted = affected.rowcount > 0
            if inserted:
                self._insert_node_metadata(node)
        return inserted

    def add_nodes(self, nodes: Iterable[GraphNode]) -> int:
        inserted = 0
        with self._connection:
            for node in nodes:
                affected = self._connection.execute(
                    """
                    INSERT OR IGNORE INTO graph_nodes
                        (node_id, node_type, label, ref_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (node.node_id, node.node_type.value, node.label, node.ref_id, node.created_at),
                )
                if affected.rowcount > 0:
                    self._insert_node_metadata(node)
                    inserted += 1
        return inserted

    def get_node(self, node_id: str) -> GraphNode:
        row = self._connection.execute(
            "SELECT * FROM graph_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        if row is None:
            raise NodeNotFoundError(f"no node with id {node_id!r}")
        return self._row_to_node(row)

    def has_node(self, node_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM graph_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return row is not None

    def list_nodes(
        self,
        *,
        node_types: frozenset[EntityType] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> builtins.list[GraphNode]:
        where = ""
        params: list[object] = []
        if node_types:
            ordered = sorted(member.value for member in node_types)
            placeholders = ", ".join("?" for _ in ordered)
            where = f" WHERE node_type IN ({placeholders})"
            params.extend(ordered)
        sql = f"SELECT * FROM graph_nodes{where} ORDER BY node_id ASC"
        sql, params = _apply_limit(sql, params, limit, offset)
        rows = self._connection.execute(sql, params).fetchall()
        return [self._row_to_node(row) for row in rows]

    def count_nodes(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0])

    # -- edges -----------------------------------------------------------------

    def add_edge(self, edge: GraphEdge) -> bool:
        with self._connection:
            return self._insert_edge(edge)

    def add_edges(self, edges: Iterable[GraphEdge]) -> int:
        inserted = 0
        with self._connection:
            for edge in edges:
                if self._insert_edge(edge):
                    inserted += 1
        return inserted

    def list_edges(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relationships: frozenset[RelationshipType] | None = None,
        limit: int | None = None,
    ) -> builtins.list[GraphEdge]:
        clauses: list[str] = []
        params: list[object] = []
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        if relationships:
            ordered = sorted(member.value for member in relationships)
            placeholders = ", ".join("?" for _ in ordered)
            clauses.append(f"relationship IN ({placeholders})")
            params.extend(ordered)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            f"SELECT * FROM graph_edges{where} "
            "ORDER BY source_id ASC, relationship ASC, target_id ASC, edge_id ASC"
        )
        sql, params = _apply_limit(sql, params, limit, 0)
        rows = self._connection.execute(sql, params).fetchall()
        return [self._row_to_edge(row) for row in rows]

    def count_edges(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0])

    def close(self) -> None:
        self._connection.close()

    # -- internal helpers ------------------------------------------------------

    def _insert_edge(self, edge: GraphEdge) -> bool:
        affected = self._connection.execute(
            """
            INSERT OR IGNORE INTO graph_edges
                (edge_id, source_id, target_id, relationship, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                edge.edge_id,
                edge.source_id,
                edge.target_id,
                edge.relationship.value,
                edge.created_at,
            ),
        )
        if affected.rowcount == 0:
            return False
        for key in sorted(edge.metadata):
            self._connection.execute(
                "INSERT INTO graph_edge_metadata (edge_id, key, value) VALUES (?, ?, ?)",
                (edge.edge_id, key, edge.metadata[key]),
            )
        return True

    def _insert_node_metadata(self, node: GraphNode) -> None:
        for key in sorted(node.metadata):
            self._connection.execute(
                "INSERT INTO graph_node_metadata (node_id, key, value) VALUES (?, ?, ?)",
                (node.node_id, key, node.metadata[key]),
            )

    def _row_to_node(self, row: sqlite3.Row) -> GraphNode:
        metadata_rows = self._connection.execute(
            "SELECT key, value FROM graph_node_metadata WHERE node_id = ? ORDER BY key ASC",
            (row["node_id"],),
        ).fetchall()
        metadata = {item["key"]: item["value"] for item in metadata_rows}
        return GraphNode(
            node_id=row["node_id"],
            node_type=EntityType(row["node_type"]),
            label=row["label"],
            ref_id=row["ref_id"],
            created_at=row["created_at"],
            metadata=metadata,
        )

    def _row_to_edge(self, row: sqlite3.Row) -> GraphEdge:
        metadata_rows = self._connection.execute(
            "SELECT key, value FROM graph_edge_metadata WHERE edge_id = ? ORDER BY key ASC",
            (row["edge_id"],),
        ).fetchall()
        metadata = {item["key"]: item["value"] for item in metadata_rows}
        return GraphEdge(
            edge_id=row["edge_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relationship=RelationshipType(row["relationship"]),
            created_at=row["created_at"],
            metadata=metadata,
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


__all__ = ["GraphStore", "SQLiteGraphStore"]
