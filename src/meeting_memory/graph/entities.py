"""Deterministic entity extraction for the memory graph.

Entities (projects, technologies, customers, teams, vendors, documents) are found
with fixed rules and configurable vocabularies — never by AI inference. Detection
is case-insensitive, word-boundary based, and fully reproducible: the same text
and vocabulary always yield the same entities.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..storage import StoredMeeting, StoredMemory
from .models import EntityType, GraphNode

# A small built-in technology lexicon so the graph is useful out of the box; the
# vocabulary below can extend or override every category.
DEFAULT_TECHNOLOGIES: frozenset[str] = frozenset(
    {
        "postgres",
        "postgresql",
        "mysql",
        "sqlite",
        "mongodb",
        "redis",
        "kafka",
        "rabbitmq",
        "elasticsearch",
        "snowflake",
        "spark",
        "hadoop",
        "python",
        "java",
        "javascript",
        "typescript",
        "go",
        "rust",
        "react",
        "vue",
        "angular",
        "django",
        "flask",
        "fastapi",
        "node",
        "docker",
        "kubernetes",
        "terraform",
        "aws",
        "gcp",
        "azure",
        "graphql",
        "grpc",
        "rest",
    }
)

_PROJECT_RE = re.compile(r"(?i:\bproject)\s+([A-Z][A-Za-z0-9]+)\b")
_CUSTOMER_RE = re.compile(r"(?i:\b(?:customer|client))\s+([A-Z][A-Za-z0-9]+)\b")
_VENDOR_RE = re.compile(r"(?i:\bvendor)\s+([A-Z][A-Za-z0-9]+)\b")
_DOCUMENT_FILE_RE = re.compile(r"\b([\w-]+\.(?:md|doc|docx|pdf|txt))\b", re.IGNORECASE)
_DOCUMENT_KEYWORDS: frozenset[str] = frozenset({"runbook", "spec", "rfc", "playbook"})


@dataclass(frozen=True)
class EntityVocabulary:
    """Configurable vocabularies for deterministic entity detection."""

    projects: frozenset[str] = frozenset()
    technologies: frozenset[str] = field(default_factory=lambda: DEFAULT_TECHNOLOGIES)
    customers: frozenset[str] = frozenset()
    teams: frozenset[str] = frozenset()
    vendors: frozenset[str] = frozenset()
    documents: frozenset[str] = frozenset()

    def _categories(self) -> tuple[tuple[EntityType, frozenset[str]], ...]:
        return (
            (EntityType.PROJECT, self.projects),
            (EntityType.TECHNOLOGY, self.technologies),
            (EntityType.CUSTOMER, self.customers),
            (EntityType.TEAM, self.teams),
            (EntityType.VENDOR, self.vendors),
            (EntityType.DOCUMENT, self.documents),
        )


DEFAULT_VOCABULARY = EntityVocabulary()


@dataclass(frozen=True)
class EntityExtraction:
    """Entities found in a meeting and which memories/meeting mention them."""

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    memory_mentions: dict[str, frozenset[str]] = field(default_factory=dict)
    meeting_mentions: frozenset[str] = frozenset()


def _contains_word(haystack_lower: str, needle: str) -> bool:
    return re.search(rf"\b{re.escape(needle.lower())}\b", haystack_lower) is not None


def detect_entities(
    text: str, vocabulary: EntityVocabulary = DEFAULT_VOCABULARY
) -> list[tuple[EntityType, str]]:
    """Return the ``(type, name)`` entities found in ``text``, sorted and unique."""
    found: set[tuple[EntityType, str]] = set()
    lowered = text.lower()

    for entity_type, terms in vocabulary._categories():
        for term in terms:
            if _contains_word(lowered, term):
                found.add((entity_type, term))

    for match in _PROJECT_RE.finditer(text):
        found.add((EntityType.PROJECT, match.group(1)))
    for match in _CUSTOMER_RE.finditer(text):
        found.add((EntityType.CUSTOMER, match.group(1)))
    for match in _VENDOR_RE.finditer(text):
        found.add((EntityType.VENDOR, match.group(1)))
    for match in _DOCUMENT_FILE_RE.finditer(text):
        found.add((EntityType.DOCUMENT, match.group(1)))
    for keyword in _DOCUMENT_KEYWORDS:
        if _contains_word(lowered, keyword):
            found.add((EntityType.DOCUMENT, keyword))

    return sorted(found, key=lambda item: (item[0].value, item[1].lower()))


def extract_entities(
    meeting: StoredMeeting,
    memories: Sequence[StoredMemory],
    vocabulary: EntityVocabulary = DEFAULT_VOCABULARY,
) -> EntityExtraction:
    """Extract entity nodes and mention maps from a meeting and its memories."""
    created_at = meeting.created_at
    nodes: dict[str, GraphNode] = {}
    memory_mentions: dict[str, frozenset[str]] = {}
    meeting_mentions: set[str] = set()

    def register(entity_type: EntityType, name: str) -> str:
        node = GraphNode.for_entity(entity_type, name, created_at=created_at)
        nodes.setdefault(node.node_id, node)
        return node.node_id

    for entity_type, name in detect_entities(meeting.title or "", vocabulary):
        meeting_mentions.add(register(entity_type, name))

    for memory in memories:
        mention_ids: set[str] = set()
        for entity_type, name in detect_entities(memory.text, vocabulary):
            node_id = register(entity_type, name)
            mention_ids.add(node_id)
            meeting_mentions.add(node_id)
        if mention_ids:
            memory_mentions[memory.memory_id] = frozenset(mention_ids)

    return EntityExtraction(
        nodes=nodes,
        memory_mentions=memory_mentions,
        meeting_mentions=frozenset(meeting_mentions),
    )


__all__ = [
    "DEFAULT_TECHNOLOGIES",
    "DEFAULT_VOCABULARY",
    "EntityExtraction",
    "EntityVocabulary",
    "detect_entities",
    "extract_entities",
]
