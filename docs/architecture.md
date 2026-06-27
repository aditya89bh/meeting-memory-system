# Architecture

This page collects the system's architecture as a set of diagrams. Every diagram is
authored in [Mermaid](https://mermaid.js.org/) so it renders directly on GitHub and in
the MkDocs documentation site. See [Exporting diagrams](#exporting-diagrams) to produce
PNG/SVG assets from these sources.

The Meeting Memory System is a deterministic, local-first pipeline. There are no
external services and no LLM calls: every transcript is turned into structured,
queryable institutional memory by rule-based extraction and analysis.

## Overall architecture

```mermaid
flowchart TB
    subgraph Interfaces
        CLI[CLI<br/>meeting-memory]
        API[REST API<br/>FastAPI]
        SDK[Python SDK<br/>MeetingMemoryClient]
        DASH[Web dashboard]
    end

    subgraph Services["Service layer"]
        MS[MeetingService]
        RS[RetrievalService]
        GS[GraphService]
        IS[IntelligenceService]
        AS[AutomationService]
        ES[ExportService]
    end

    subgraph Core["Core pipeline"]
        PAR[Parser]
        EXT[Extraction]
        RET[Retrieval engine]
        GRAPH[Graph builder]
        INTEL[Intelligence engine]
    end

    subgraph Platform
        STORE[(SQLite store)]
        CONN[Connector framework]
        OBS[Observability]
        REC[Backup & recovery]
    end

    CLI --> Services
    API --> Services
    SDK --> Services
    DASH --> API

    MS --> PAR --> EXT --> STORE
    RS --> RET --> STORE
    GS --> GRAPH --> STORE
    IS --> INTEL --> STORE
    AS --> CONN
    ES --> STORE

    CONN --> MS
    OBS -.instruments.-> Services
    REC -.snapshots.-> STORE
```

## Data flow

How a raw transcript becomes queryable memory and intelligence.

```mermaid
flowchart LR
    T[Transcript<br/>txt / json / md / csv] --> P[Parse<br/>meeting + utterances]
    P --> E[Extract<br/>typed memories]
    E --> D[Deduplicate<br/>content hash]
    D --> S[(Persist<br/>SQLite)]
    S --> R[Retrieve<br/>ranked search]
    S --> G[Build graph<br/>nodes + edges]
    S --> I[Analyze<br/>insights + health]
    R --> O1[Answers]
    G --> O2[Relationships]
    I --> O3[Reports]
```

## Service layer

The service layer is the single reusable surface shared by the CLI, REST API, and SDK.
Each service wraps the core pipeline and the store with a stable, typed contract.

```mermaid
flowchart TB
    subgraph Callers
        CLI
        API
        SDK
    end

    subgraph Services
        MS[MeetingService<br/>import · stats · timeline]
        RS[RetrievalService<br/>search · explain]
        GS[GraphService<br/>summary · neighbors · path]
        IS[IntelligenceService<br/>report · render]
        AS[AutomationService<br/>jobs · schedules]
        ES[ExportService<br/>graph · snapshots]
    end

    STORE[(SQLiteMemoryStore)]

    Callers --> Services --> STORE
```

## Graph architecture

The organizational graph projects stored memories into nodes (people, projects,
meetings, decisions, risks, …) connected by typed relationships.

```mermaid
flowchart TB
    subgraph Sources
        M[Meetings]
        MEM[Memories]
        SP[Speakers]
    end

    BUILD[GraphBuilder]

    subgraph GraphModel["Graph model"]
        N{{graph_nodes}}
        EDG{{graph_edges}}
    end

    Q[Graph queries<br/>neighbors · path · summary]

    M --> BUILD
    MEM --> BUILD
    SP --> BUILD
    BUILD --> N
    BUILD --> EDG
    N --> Q
    EDG --> Q
```

```mermaid
flowchart LR
    Person -- attended --> Meeting
    Person -- owns --> Commitment
    Meeting -- produced --> Decision
    Meeting -- raised --> Risk
    Decision -- supersedes --> Decision
    Risk -- recurs_in --> Meeting
    Project -- discussed_in --> Meeting
```

## API architecture

```mermaid
flowchart TB
    Client -->|HTTP| FASTAPI[FastAPI app]
    FASTAPI --> RT[Routers<br/>meetings · search · graph · intelligence · automation]
    RT --> DEP[Dependency layer<br/>service factory + DB path]
    DEP --> SVC[Service layer]
    SVC --> STORE[(SQLite)]
    FASTAPI --> DOCS[OpenAPI /docs]
    FASTAPI --> DASH[/dashboard server-rendered/]
    FASTAPI --> HEALTH[/health/]
```

## Connector framework

Connectors are the pluggable boundary for importing transcripts from, and exporting
results to, external systems — all behind deterministic, offline interfaces.

```mermaid
flowchart TB
    subgraph Importers
        FS[Filesystem]
        JSONL[JSON / JSONL]
        CSVI[CSV]
        MDI[Markdown]
    end

    REG[Connector registry<br/>config-driven]

    subgraph Exporters
        JSONE[JSON]
        GRAPHE[Graph export]
        SNAP[Snapshot]
    end

    Importers --> REG --> MS[MeetingService]
    IS[IntelligenceService] --> REG --> Exporters
```

## Automation pipeline

```mermaid
flowchart LR
    SCH[Scheduler] --> JOB[Job definition<br/>source + action]
    JOB --> RUN[Job run]
    RUN --> IMP[Import new transcripts]
    IMP --> ANALYZE[Refresh graph + intelligence]
    ANALYZE --> EXPORT[Export / notify]
    RUN --> LOG[(Job logs)]
    LOG --> AUDIT[jobs · logs commands]
```

## Request lifecycle

End-to-end path of a single `POST /search` request.

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI app
    participant D as Dependency layer
    participant S as RetrievalService
    participant R as Retrieval engine
    participant DB as SQLite

    C->>A: POST /search {query, limit}
    A->>D: resolve service (DB path)
    D->>S: RetrievalService(db)
    S->>R: plan + rank query
    R->>DB: read candidate memories
    DB-->>R: rows
    R-->>S: ranked results
    S-->>A: response model
    A-->>C: 200 JSON {ranked, explanation}
```

## Exporting diagrams

The Mermaid sources above are the source of truth. To render standalone SVG/PNG assets
(for slides or printed docs), use the Mermaid CLI:

```bash
npm install -g @mermaid-js/mermaid-cli
# Extract a diagram into diagram.mmd, then:
mmdc -i diagram.mmd -o diagram.svg
mmdc -i diagram.mmd -o diagram.png -b transparent
```

GitHub and the MkDocs site render these diagrams natively, so exported assets are only
needed for environments without Mermaid support.
