"""Deterministic exporters for the organizational memory graph.

The graph can be rendered as JSON (for tooling), Mermaid (for docs and quick
diagrams), or Graphviz DOT (for richer rendering). All exporters sort nodes and
edges and include node and edge labels, so the output is stable and diff-friendly.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import RELATIONSHIP_REGISTRY, GraphEdge, GraphNode

EXPORT_FORMATS: tuple[str, ...] = ("json", "mermaid", "dot")

_LABEL_LIMIT = 48


def _sorted_nodes(nodes: Sequence[GraphNode]) -> list[GraphNode]:
    return sorted(nodes, key=lambda node: node.node_id)


def _sorted_edges(edges: Sequence[GraphEdge]) -> list[GraphEdge]:
    return sorted(
        edges,
        key=lambda edge: (edge.source_id, edge.relationship.value, edge.target_id, edge.edge_id),
    )


def _node_label(node: GraphNode) -> str:
    text = " ".join(node.label.split())
    if len(text) > _LABEL_LIMIT:
        text = text[: _LABEL_LIMIT - 1].rstrip() + "…"
    return f"{node.node_type.value}: {text}"


def _edge_label(edge: GraphEdge) -> str:
    descriptor = RELATIONSHIP_REGISTRY.get(edge.relationship)
    return descriptor.label if descriptor else edge.relationship.value


def to_json(nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]) -> dict[str, object]:
    """Serialise the graph into a JSON-compatible dictionary."""
    return {
        "nodes": [node.to_dict() for node in _sorted_nodes(nodes)],
        "edges": [edge.to_dict() for edge in _sorted_edges(edges)],
    }


def to_mermaid(nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]) -> str:
    """Render the graph as a Mermaid ``graph TD`` diagram."""
    ordered_nodes = _sorted_nodes(nodes)
    alias = {node.node_id: f"n{index}" for index, node in enumerate(ordered_nodes)}
    lines = ["graph TD"]
    for node in ordered_nodes:
        label = _node_label(node).replace('"', "'")
        lines.append(f'    {alias[node.node_id]}["{label}"]')
    for edge in _sorted_edges(edges):
        if edge.source_id not in alias or edge.target_id not in alias:
            continue
        label = _edge_label(edge).replace("|", "/")
        lines.append(f"    {alias[edge.source_id]} -->|{label}| {alias[edge.target_id]}")
    return "\n".join(lines) + "\n"


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]) -> str:
    """Render the graph as a Graphviz DOT digraph."""
    lines = ["digraph memory_graph {", "    rankdir=LR;"]
    for node in _sorted_nodes(nodes):
        label = _dot_escape(_node_label(node))
        lines.append(f'    "{_dot_escape(node.node_id)}" [label="{label}"];')
    for edge in _sorted_edges(edges):
        label = _dot_escape(_edge_label(edge))
        lines.append(
            f'    "{_dot_escape(edge.source_id)}" -> "{_dot_escape(edge.target_id)}" '
            f'[label="{label}"];'
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def export_graph(
    nodes: Sequence[GraphNode], edges: Sequence[GraphEdge], fmt: str
) -> str | dict[str, object]:
    """Export the graph in ``fmt`` (``json``, ``mermaid``, or ``dot``)."""
    if fmt == "json":
        return to_json(nodes, edges)
    if fmt == "mermaid":
        return to_mermaid(nodes, edges)
    if fmt == "dot":
        return to_dot(nodes, edges)
    raise ValueError(f"unknown export format {fmt!r}; choose from: {', '.join(EXPORT_FORMATS)}")


__all__ = ["EXPORT_FORMATS", "export_graph", "to_dot", "to_json", "to_mermaid"]
