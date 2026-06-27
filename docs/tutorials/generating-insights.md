# Tutorial 5 — Generating insights

The intelligence layer analyses stored memory to surface recurring risks, revisited
decisions, stale commitments, and an overall organizational health score — all with
deterministic, rule-based analysis.

## Setup

```bash
meeting-memory import-dir examples/organizations/research-lab --db helix.db --recursive
```

## Generate a full report

```bash
meeting-memory report --db helix.db
```

The report includes an executive summary, health score, insights grouped by category,
and prioritized recommendations.

## Insights, metrics, and recommendations separately

```bash
meeting-memory insights --db helix.db          # discovered insights
meeting-memory metrics --db helix.db           # health metrics
meeting-memory recommendations --db helix.db   # prioritized actions
```

## What the analysis finds

- **Recurring risks** — the same risk appearing across multiple meetings while still
  unresolved (e.g. *"reagent batch variability"*).
- **Revisited decisions** — a decision discussed in several meetings without a durable
  resolution.
- **Stale commitments** — action items open for a long time or with low resolution rates.
- **Ownership concentration** — individuals carrying many open commitments.

## Render formats

```bash
meeting-memory report --db helix.db --format markdown
meeting-memory metrics --db helix.db --format json
meeting-memory report --db helix.db --format markdown -o report.md
```

Narrow the analysis to a single project or person:

```bash
meeting-memory report --db helix.db --project "Protein Folding Study"
meeting-memory report --db helix.db --person Mara
```

Next: [Running automation](running-automation.md).
