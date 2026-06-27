"""Organizational Memory Graph (Phase 5).

Links meetings, memories, people, and extracted entities (projects, customers,
technologies, teams, vendors, documents) into a typed, directed graph persisted
in the existing SQLite database. The whole layer is deterministic and uses only
the standard library: no LLM APIs, no embeddings or vector databases, and no
external graph databases.
"""

from __future__ import annotations

from .builder import GraphBuildResult, build_graph
from .engine import MEMORY_NODE_TYPES, GraphEngine
from .entities import (
    DEFAULT_VOCABULARY,
    EntityExtraction,
    EntityVocabulary,
    detect_entities,
    extract_entities,
)
from .lineage import decision_lineage, relationship_lineage, risk_lineage
from .linking import cross_meeting_edges
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
    "MEMORY_NODE_TYPES",
    "RELATIONSHIP_REGISTRY",
    "EntityExtraction",
    "EntityType",
    "EntityVocabulary",
    "GraphBuildResult",
    "GraphEdge",
    "GraphEngine",
    "GraphNode",
    "GraphPath",
    "GraphQuery",
    "GraphRelationship",
    "GraphResult",
    "GraphStore",
    "RelationshipType",
    "SQLiteGraphStore",
    "build_graph",
    "cross_meeting_edges",
    "decision_lineage",
    "detect_entities",
    "extract_entities",
    "relationship_lineage",
    "risk_lineage",
    "slugify",
]
