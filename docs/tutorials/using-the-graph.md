# Tutorial 4 — Using the graph

The organizational graph connects people, projects, meetings, decisions, and risks so
you can explore relationships rather than isolated facts.

## Setup

```bash
meeting-memory import-dir examples/organizations/saas --db lumen.db --recursive
```

## Summarize the graph

```bash
meeting-memory graph --db lumen.db
```

This prints node and edge counts and a breakdown by node type and relationship.

## Explore neighbors

Find everything directly connected to a node:

```bash
meeting-memory neighbors <node-id> --db lumen.db --depth 1
```

Increase `--depth` to widen the exploration. Use `meeting-memory graph` to discover node
ids to start from.

## Find a path between two nodes

```bash
meeting-memory path <source-id> <target-id> --db lumen.db
```

This returns the shortest relationship path connecting two entities — for example, how a
person is connected to a decision through a meeting.

## Export the graph

To analyse the graph in another tool or visualize it:

```bash
meeting-memory export-graph --db lumen.db --format json > graph.json
```

`--format` also supports `mermaid` and `dot` for direct rendering. The export contains
nodes (with type and label) and typed edges, suitable for loading into graph viewers or
notebooks. See [`notebooks/03_graph.ipynb`](https://github.com/aditya89bh/meeting-memory-system/blob/main/notebooks/03_graph.ipynb)
for an interactive walkthrough.

Next: [Generating insights](generating-insights.md).
