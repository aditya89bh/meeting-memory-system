# Case study — Decision reversals

**Dataset:** [`examples/organizations/enterprise`](../../examples/organizations/enterprise/)

## Problem

Orion's platform team is running a large cloud migration. The migration approach keeps
changing — and each change is reasonable in isolation — but nobody has a consolidated
view of how often the direction has shifted or whether the top-level priority is actually
settled. Repeatedly reopened decisions quietly burn engineering time and erode
confidence in the plan.

## Input meetings

Three program meetings on the Orion migration:

- **2026-01-12 — Program Review**: the migration is declared the program's top priority;
  approach is a *lift-and-shift to the cloud*.
- **2026-02-02 — Architecture Sync**: the same top-priority decision is restated, but the
  approach changes to *containerize every service*.
- **2026-02-23 — Wave One Retro**: the approach changes again to *managed Kubernetes* for
  the remaining waves.

## Analysis

```bash
meeting-memory import-dir examples/organizations/enterprise --db orion.db --recursive
meeting-memory report --db orion.db
```

The intelligence engine detects a decision that is discussed across multiple meetings
without a durable resolution, and flags it as revisited.

## Output

```
[medium] (decision) Decision revisited across 2 meetings
```

## Insights

- The standing "cloud migration is the top priority" decision was re-litigated across
  meetings rather than ratified once and referenced thereafter.
- The migration *approach* evolved through three distinct technical strategies in six
  weeks (lift-and-shift → containers → managed Kubernetes), trackable through the
  meeting timeline (`meeting-memory timeline`).
- Each pivot was locally sensible, but the pattern is only visible across meetings.

## Recommendations

> **Settle a repeatedly revisited decision.** Assign a clear owner and close the topic
> with a documented outcome.

Distinguish the stable *intent* (migrate to the cloud) from the *implementation choice*
(which runtime). Ratify the intent once, then record runtime changes as explicit
supersessions so the history reads as deliberate evolution rather than churn.
