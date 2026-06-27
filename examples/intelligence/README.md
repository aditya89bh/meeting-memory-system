# Organizational intelligence example

Phase 6 turns the stored organizational memory into deterministic insights,
metrics, recommendations, and reports. It runs on the same database the rest of
the system builds, so no extra data format is needed — import transcripts, then
analyse.

This example reuses the three Project Atlas meetings from
[`examples/history`](../history/README.md), which span two weeks and contain a
risk that recurs every meeting and a teammate who keeps picking up commitments.

## Build the database

```bash
meeting-memory import examples/history/meeting1.txt --db atlas.db
meeting-memory import examples/history/meeting2.txt --db atlas.db
meeting-memory import examples/history/meeting3.txt --db atlas.db
```

## Discover insights

```bash
meeting-memory insights --db atlas.db
```

```
[medium] (person) Marco owns 3 open commitments
    Marco is responsible for 3 unresolved commitments, indicating a possible workload bottleneck.
[medium] (risk) Risk recurred in 3 meetings
    “There is a risk that the vendor API rate limits will slow ingestion.” has appeared in 3 meetings and is still unresolved.
```

The recurring vendor-API risk demonstrates **recurring risks**, and Marco's
three open items demonstrate **commitment overload**. Both are computed from the
graph and storage layers — nothing is hard-coded.

## Health metrics

```bash
meeting-memory metrics --db atlas.db
```

```
Reference date: 2026-02-16
Overall health: 0.5476
Scores:
  avg_resolution_days: 0
  commitment_completion: 0
  cross_team_collaboration: 1
  decision_stability: 1
  knowledge_reuse: 0.2857
  meeting_productivity: 1
  repeated_discussion_rate: 0.1304
  risk_density: 1
  risk_resolution: 0
```

`knowledge_reuse` and `repeated_discussion_rate` quantify **knowledge reuse** —
how often the same content resurfaces across meetings.

## Recommendations

```bash
meeting-memory recommendations --db atlas.db
```

```
[medium] (person) Rebalance an overloaded owner
    Redistribute or de-scope commitments to relieve the bottleneck. ...
[medium] (risk) Mitigate a recurring risk
    Create an owned mitigation plan so the risk stops resurfacing. ...
```

## Organization-wide report

```bash
# Plain text (default), Markdown, or JSON
meeting-memory report --db atlas.db --format markdown --output atlas-report.md
meeting-memory report --db atlas.db --format json
```

## Focusing the analysis

Every command accepts `--project`, `--person`, and `--meeting` filters:

```bash
# Only Marco's slice of the organization
meeting-memory insights --db atlas.db --person Marco

# Only a specific insight type, as JSON
meeting-memory insights --db atlas.db --type recurring_risk --json
```

## Seeing decision reversals and project hotspots

`decision reversals` (repeatedly superseded decisions) appear once decisions are
superseded via `meeting-memory` lifecycle transitions, and `project bottlenecks`
(risk hotspots / recurring blockers) appear when risks and decisions name a
project (for example "Project Atlas"). With those present, `insights` adds
`repeatedly_superseded_decision`, `risk_hotspot`, and `project_blocker` entries.
