"""Graph endpoints: summary, neighbourhood traversal, and path finding."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from ...graph import EntityType, RelationshipType
from ..dependencies import GraphServiceDep
from ..schemas import GraphResponse, NeighborsResponse, PathResponse

router = APIRouter(prefix="/graph", tags=["graph"])


def _entity_types(values: list[EntityType] | None) -> frozenset[EntityType] | None:
    return frozenset(values) if values else None


def _relationships(values: list[RelationshipType] | None) -> frozenset[RelationshipType] | None:
    return frozenset(values) if values else None


@router.get("", response_model=GraphResponse, summary="Graph summary")
def graph_summary(
    service: GraphServiceDep,
    node_type: Annotated[list[EntityType] | None, Query(alias="type")] = None,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> GraphResponse:
    """Build the graph and return node/edge counts plus a node listing."""
    summary = service.summary(node_types=_entity_types(node_type), limit=limit)
    return GraphResponse.from_domain(summary)


@router.get("/neighbors", response_model=NeighborsResponse, summary="Node neighbourhood")
def neighbors(
    service: GraphServiceDep,
    node_id: Annotated[str, Query(description="Node id to traverse from.")],
    depth: Annotated[int, Query(ge=1, le=6)] = 1,
    node_type: Annotated[list[EntityType] | None, Query(alias="type")] = None,
    relationship: Annotated[list[RelationshipType] | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> NeighborsResponse:
    """Traverse the graph from a node and return its neighbourhood."""
    result = service.neighbors(
        node_id,
        depth=depth,
        relationships=_relationships(relationship),
        node_types=_entity_types(node_type),
        limit=limit,
    )
    return NeighborsResponse.from_domain(result)


@router.get("/path", response_model=PathResponse, summary="Shortest path")
def path(
    service: GraphServiceDep,
    source: Annotated[str, Query(description="Source node id.")],
    target: Annotated[str, Query(description="Target node id.")],
    depth: Annotated[int, Query(ge=1, le=12)] = 6,
    relationship: Annotated[list[RelationshipType] | None, Query()] = None,
) -> PathResponse:
    """Return a deterministic shortest path between two nodes, if one exists."""
    found = service.path(
        source, target, max_depth=depth, relationships=_relationships(relationship)
    )
    if found is None:
        return PathResponse(found=False)
    payload = found.to_dict()
    return PathResponse.model_validate({"found": True, **payload})
