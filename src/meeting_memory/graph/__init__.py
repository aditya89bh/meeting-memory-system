"""Organizational Memory Graph (Phase 5).

Links meetings, memories, people, and extracted entities (projects, customers,
technologies, teams, vendors, documents) into a typed, directed graph persisted
in the existing SQLite database. The whole layer is deterministic and uses only
the standard library: no LLM APIs, no embeddings or vector databases, and no
external graph databases.
"""

from __future__ import annotations

from .entities import (
    DEFAULT_VOCABULARY,
    EntityExtraction,
    EntityVocabulary,
    detect_entities,
    extract_entities,
)
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
    "DEFAULT_VOCABULARY",
    "RELATIONSHIP_REGISTRY",
    "EntityExtraction",
    "EntityType",
    "EntityVocabulary",
    "GraphEdge",
    "GraphNode",
    "GraphPath",
    "GraphQuery",
    "GraphRelationship",
    "GraphResult",
    "GraphStore",
    "RelationshipType",
    "SQLiteGraphStore",
    "detect_entities",
    "extract_entities",
    "slugify",
]
