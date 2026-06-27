# Case study — Knowledge reuse

**Dataset:** [`examples/organizations/research-lab`](../../examples/organizations/research-lab/)

## Problem

Helix Bio Lab runs studies that must be reproducible months or years later. Decisions
about methods, reagent suppliers, and analysis pipelines are made in lab meetings and
then forgotten — so the next study re-derives the same hard-won practices from scratch,
or worse, silently diverges from them.

## Input meetings

Three lab meetings on the protein folding study:

- **2026-01-09 — Lab Meeting**: reproducibility is declared the lab's top priority;
  triplicate runs required.
- **2026-01-30 — Methods Review**: switch the assay to the core facility instrument;
  publish a version-pinned analysis pipeline; pre-register the analysis plan.
- **2026-02-20 — Results Review**: confirmatory assay at two independent sites; pipeline
  published and version pinned; onboard a backup reagent supplier.

## Analysis

```bash
meeting-memory import-dir examples/organizations/research-lab --db helix.db --recursive
meeting-memory search "reproducibility" --db helix.db
meeting-memory report --db helix.db
```

Searching memory turns the lab's accumulated practices into a reusable knowledge base:
the same query surfaces every decision, commitment, and risk related to reproducibility
across all meetings.

## Output

```
[medium] (decision) Decision revisited across 2 meetings
[medium] (risk)     Risk recurred in 2 meetings
```

(plus a searchable trail: triplicate runs, version-pinned pipeline, pre-registration,
multi-site confirmation, backup supplier.)

## Insights

- The lab's reproducibility playbook is now queryable: a single search returns the
  protocol decisions and the commitments that operationalized them.
- The reagent-variability risk and its mitigation (validate lots against a reference
  standard, add a backup supplier) are captured together, so the next study inherits the
  fix instead of rediscovering the problem.
- The version-pinned analysis pipeline commitment is preserved as institutional memory,
  not tribal knowledge.

## Recommendations

> **Settle a repeatedly revisited decision** and **mitigate a recurring risk** — then
> reuse them.

Treat the captured memory as a starting checklist for the next study: import the new
study's meetings into the same database and the prior practices remain one search away.
