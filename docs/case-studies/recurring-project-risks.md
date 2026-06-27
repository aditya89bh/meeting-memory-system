# Case study — Recurring project risks

**Dataset:** [`examples/organizations/saas`](../../examples/organizations/saas/)

## Problem

Lumen, a growing SaaS company, holds frequent engineering and leadership meetings. The
same reliability concern keeps coming up, but because it lives in scattered notes nobody
notices that it has been raised repeatedly without ever being closed. By the time it
causes an incident, it looks like a surprise — even though the team had flagged it for
weeks.

## Input meetings

Three meetings over six weeks on the Insights Platform:

- **2026-01-08 — Growth Review**: "There is a risk that query latency will degrade as
  tenant data grows."
- **2026-01-29 — Scaling Sync**: the *same* latency risk is raised again, with a
  proposed mitigation (read replicas, partitioning).
- **2026-02-19 — Pilot Retro**: the risk is finally reported as mitigated.

## Analysis

```bash
meeting-memory import-dir examples/organizations/saas --db lumen.db --recursive
meeting-memory insights --db lumen.db
```

The system hashes the content of every extracted memory and groups identical items that
appear across more than one meeting. The latency risk appears in two distinct meetings
while still unresolved, so it is surfaced as a recurring risk.

## Output

```
[medium] (risk) Risk recurred in 2 meetings
[medium] (risk) Risk unresolved for 42 days
```

## Insights

- A single risk — query latency under tenant growth — was raised in two separate
  meetings before any owner was assigned.
- The risk remained unresolved for the full window between when it was first raised and
  the analysis reference date.
- The recurrence was invisible in any single meeting; it only emerges when memory spans
  meetings.

## Recommendations

> **Mitigate a recurring risk.** Create an owned mitigation plan so the risk stops
> resurfacing. The latency risk appeared in two meetings and is still unresolved.

Concretely: assign an owner the first time a risk recurs, attach a dated mitigation
commitment, and let the next retro confirm closure — exactly the arc this dataset ends
on once partitioning lands.
