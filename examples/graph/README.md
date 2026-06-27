# Organizational graph examples

These examples build the organizational memory graph from the three Project Atlas
transcripts in [`examples/history`](../history). Import them into one database
first; the `--now` flag keeps timestamps reproducible.

```bash
meeting-memory import examples/history/meeting1.txt --db atlas.db --now 2026-03-01T00:00:00+00:00
meeting-memory import examples/history/meeting2.txt --db atlas.db --now 2026-03-01T00:00:00+00:00
meeting-memory import examples/history/meeting3.txt --db atlas.db --now 2026-03-01T00:00:00+00:00
```

Every graph command rebuilds the graph from the store first (idempotently), so it
always reflects the current memories — no separate build step is required.

## Overview — what is in the graph?

```bash
meeting-memory graph --db atlas.db
```

```
Nodes: 38
Edges: 100
By node type:
  assumption: 3
  commitment: 3
  decision: 6
  document: 1
  fact: 8
  meeting: 3
  memory: 2
  person: 3
  project: 1
  question: 3
  risk: 3
  technology: 1
  vendor: 1
By relationship:
  assigned_to: 3
  connected_to: 14
  discussed_in: 28
  mentions: 27
  owned_by: 28
```

## Cross-meeting link — which meetings discussed Project Atlas?

`Atlas` is a single shared node, so every meeting that mentions it points at the
same node. This is the cross-meeting linking in action.

```bash
meeting-memory neighbors project:atlas --db atlas.db --type meeting
```

```
node: project:atlas  [project]  Atlas
neighbors (3):
  meeting:meeting1  [meeting]  Project Atlas Kickoff
  meeting:meeting2  [meeting]  Project Atlas Weekly Sync
  meeting:meeting3  [meeting]  Project Atlas Beta Review
```

## Customer relationships — show everything related to a node

```bash
meeting-memory neighbors meeting:meeting1 --db atlas.db --depth 1
```

## Technology dependencies — what does Atlas depend on?

```bash
meeting-memory neighbors project:atlas --db atlas.db --type technology
```

## Path search — how are two nodes connected?

```bash
meeting-memory path person:lena project:atlas --db atlas.db
```

```
path (length 2):
  person:lena  [person]  Lena
  -mentions->
  meeting:meeting1  [meeting]  Project Atlas Kickoff
  -mentions->
  project:atlas  [project]  Atlas
```

## Decision evolution — lineage of superseded decisions

When a stored decision is superseded by a newer one, the graph records a
`SUPERSEDES` edge and `meeting-memory neighbors` / the engine's lineage helpers
order the chain oldest-to-newest. (Supersede memories with `meeting-memory` then
rebuild to see the chain grow.)

## Export — render the graph

```bash
meeting-memory export-graph --db atlas.db --format mermaid --type meeting,project
```

```
graph TD
    n0["meeting: Project Atlas Kickoff"]
    n1["meeting: Project Atlas Weekly Sync"]
    n2["meeting: Project Atlas Beta Review"]
    n3["project: Atlas"]
    n0 -->|mentions| n3
    n1 -->|mentions| n3
    n2 -->|mentions| n3
```

```bash
meeting-memory export-graph --db atlas.db --format dot > atlas.dot
meeting-memory export-graph --db atlas.db --format json > atlas.graph.json
```

The whole graph is derived deterministically from stored memories using fixed
rules and vocabularies — no language model, embeddings, or external graph database
is involved.
