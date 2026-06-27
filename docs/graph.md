# Organizational memory graph (Phase 5)

Phase 5 links the persistent store from Phase 3 into a typed, directed
**organizational memory graph**. It connects meetings, memories, people, and
extracted entities (projects, customers, technologies, teams, vendors, documents)
so the system can answer relationship questions that span many meetings:

- Which meetings discussed Project Alpha?
- Which risks are connected to this decision?
- Which commitments eventually resolved this issue?
- How has a decision evolved over time?
- Which people repeatedly collaborate?
- Which projects share common blockers?
- Show everything related to Customer ABC.

Like every other layer, the graph is **deterministic** and standard-library only:
the same store always produces the same nodes, edges, and traversals. There are no
LLM APIs, embeddings, vector databases, or external graph databases (Neo4j, etc.).

## Architecture

```
meeting_memory/graph/
├── models.py         # EntityType, RelationshipType, GraphNode/Edge/Path/Query/Result
├── store.py          # GraphStore + SQLiteGraphStore (same SQLite database)
├── entities.py       # deterministic entity extraction (vocabularies + rules)
├── relationships.py  # intra-meeting structural and semantic edges
├── linking.py        # cross-meeting linking (repeated content, resolves, collaboration)
├── builder.py        # build_graph: store ▶ nodes + edges (idempotent)
├── engine.py         # GraphEngine: neighbors / related / find_path / components
├── lineage.py        # decision and risk lineage chains
└── export.py         # JSON / Mermaid / Graphviz DOT exporters
```

The graph layer depends only on the storage layer's public interface
(`MemoryStore`, `StoredMemory`, `StoredMeeting`). It persists into the same
database file via additive tables.

## Schema

Migration version 2 adds four tables and their indexes without touching the
Phase 1–3 schema, so existing databases upgrade in place (`PRAGMA user_version`):

| Table                 | Purpose                                                   |
| --------------------- | --------------------------------------------------------- |
| `graph_nodes`         | One row per node: `node_id`, `node_type`, `label`, `ref_id` |
| `graph_edges`         | Directed edges: `edge_id`, `source_id`, `target_id`, `relationship` |
| `graph_node_metadata` | Generic key/value rows for node properties                |
| `graph_edge_metadata` | Generic key/value rows for edge properties / timestamps   |

Indexes cover `node_type`, edge `source_id`/`target_id`/`relationship`, and the
metadata owners for efficient traversal.

Node and edge ids are **deterministic functions of content**:

- `node_id = "{type}:{ref}"` — e.g. `meeting:meeting1`, `decision:m1:decision:1`,
  `person:alice`, `project:atlas`.
- `edge_id = sha1(source | relationship | target | discriminator)`.

Because ids are content-derived and writes use `INSERT OR IGNORE`, rebuilding the
graph is idempotent and **append-only**: old relationships are never overwritten.

## Entity extraction

`entities.py` finds entities with fixed rules and a configurable
`EntityVocabulary` (projects, technologies, customers, teams, vendors, documents):

- **Vocabulary terms** are matched case-insensitively on word boundaries. A
  built-in technology lexicon (`postgres`, `redis`, `kafka`, `python`, …) ships by
  default; every category can be extended.
- **Patterns** capture `Project X`, `customer/client X`, and `vendor X`
  (capitalised names), document file names (`*.md`, `*.pdf`, …), and document
  keywords (`runbook`, `spec`, `rfc`, `playbook`).

Entities are extracted from the meeting title and each memory's text, producing
entity nodes plus a per-memory and per-meeting *mention* map. No AI inference is
involved.

## Relationship extraction

`relationships.py` builds the intra-meeting edges deterministically:

| Edge                                   | When                                              |
| -------------------------------------- | ------------------------------------------------- |
| memory `DISCUSSED_IN` meeting          | always                                            |
| memory `OWNED_BY` person               | the memory has a speaker                           |
| commitment `ASSIGNED_TO` person        | commitment owner (or speaker as fallback)         |
| meeting `MENTIONS` person/entity       | participants and mentioned entities               |
| memory `MENTIONS` entity               | the entity appears in the memory text             |
| decision `RELATES_TO` project          | a decision mentions a project                     |
| risk `BLOCKS` project                  | a risk mentions a project                         |
| fact `REFERENCES` customer             | a fact mentions a customer                        |
| project `DEPENDS_ON` technology        | a memory co-mentions a project and a technology   |
| question `RELATES_TO` decision         | same meeting, sharing a mentioned entity          |
| assumption `SUPPORTS` decision         | same meeting, sharing a mentioned entity          |

The builder additionally derives `SUPERSEDES` edges from each memory's stored
`superseded_by` pointer (newer → older).

## Cross-meeting linking

`linking.py` connects meetings across time without overwriting history:

- **Shared entities.** Projects, customers, and technologies are global nodes, so
  the same entity referenced in several meetings is one node — that is the primary
  cross-meeting link and answers "which meetings discussed Project Atlas?".
- **Repeated content.** Memories with the same content hash in different meetings
  are chained with `CONNECTED_TO` (newer → older), capturing a risk/decision that
  recurs week after week.
- **Resolution.** A commitment that shares an entity with an *earlier*
  risk/open-loop gets a `RESOLVES` edge.
- **Collaboration.** Co-participants of a meeting are linked with `CONNECTED_TO`
  (one edge per shared meeting), so frequent collaborators accumulate edges.

## Graph traversal

`GraphEngine` wraps a read-only `GraphStore` and is fully deterministic — every
expansion visits neighbours in sorted order:

- `neighbors(node_id, depth, relationships, direction, node_types, limit)` — the
  nodes and edges within *depth* hops.
- `incoming` / `outgoing` — directed edges of a node.
- `related(...)` and `related_memories` / `related_meetings` / `related_people` /
  `related_projects` — reachable nodes filtered by type.
- `find_path(source, target, max_depth, relationships)` — the shortest path
  (BFS), with lexicographic tie-breaks.
- `connected_components(relationships)` — undirected components, each a sorted id
  list, components ordered by their first id.

## Lineage

`lineage.py` follows a single relationship in both directions and returns the
chain ordered **oldest-to-newest**. An edge always points from the newer node to
the older one, so one routine serves both:

- `decision_lineage(node)` follows `SUPERSEDES` (decision A → B → C).
- `risk_lineage(node)` follows `CONNECTED_TO` (a recurring risk across meetings).
- `relationship_lineage(node, relationship)` generalises to any relationship.

```
Decision A ──SUPERSEDES──▶ Decision B ──SUPERSEDES──▶ Decision C
(oldest)                                              (newest)
```

## Export

`export.py` renders the graph for tooling and documentation, with node and edge
labels and stable sorted ordering:

- `to_json(nodes, edges)` — a `{"nodes": [...], "edges": [...]}` dictionary.
- `to_mermaid(nodes, edges)` — a `graph TD` diagram (dangling edges skipped).
- `to_dot(nodes, edges)` — a Graphviz `digraph` with escaped labels.

## CLI

```bash
meeting-memory graph        --db atlas.db [--type T1,T2] [--limit N] [--json]
meeting-memory neighbors ID --db atlas.db [--depth N] [--type ...] [--relationship ...] [--json]
meeting-memory path A B     --db atlas.db [--depth N] [--relationship ...] [--json]
meeting-memory export-graph --db atlas.db --format {json,mermaid,dot} [--type ...] [--limit N]
```

Each command rebuilds the graph from the store first (idempotently), so a database
imported before Phase 5 gets a graph automatically with no re-import.

## Future graph-reasoning extensions

The deterministic graph is a foundation a richer reasoning layer can build on
without changing the schema:

- **Semantic entity resolution** — merge `Postgres`/`PostgreSQL`/`postgres db`
  into one node (today they merge only when their slugs match).
- **Weighted / scored edges** — rank relationships by frequency or recency for
  "strongest collaborators" or "most blocked project" queries.
- **Inferred resolution and lineage** — use an LLM-backed pass to link a
  commitment to the specific risk it resolved, beyond shared-entity heuristics.
- **Temporal subgraphs** — snapshot the graph at a date to see how the
  organization's memory looked at any point in time.

Each would slot in behind the existing `GraphStore`/`GraphEngine` interfaces while
keeping the deterministic core intact.
