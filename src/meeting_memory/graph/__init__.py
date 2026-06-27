"""Organizational Memory Graph (Phase 5).

Links meetings, memories, people, and extracted entities (projects, customers,
technologies, teams, vendors, documents) into a typed, directed graph persisted
in the existing SQLite database. The whole layer is deterministic and uses only
the standard library: no LLM APIs, no embeddings or vector databases, and no
external graph databases.
"""

from __future__ import annotations

from .models import (
    RELATIONSHIP_REGISTRY,
    EntityType,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphRelationship,
    GraphResult,
    RelationshipType,
    slugify,
)
from .store import GraphStore, SQLiteGraphStore

__all__ = [
    "RELATIONSHIP_REGISTRY",
    "EntityType",
    "GraphEdge",
    "GraphNode",
    "GraphPath",
    "GraphQuery",
    "GraphRelationship",
    "GraphResult",
    "GraphStore",
    "RelationshipType",
    "SQLiteGraphStore",
    "slugify",
]
