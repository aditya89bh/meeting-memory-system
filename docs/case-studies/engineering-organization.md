# Case study — Engineering organization

**Dataset:** [`examples/organizations/enterprise`](../../examples/organizations/enterprise/)

## Problem

As Orion's migration program scales across many services and several engineers, leaders
lose visibility into who is carrying what, which commitments are aging, and whether
reliability work is keeping pace. Status is spread across people's heads and meeting
notes, so bottlenecks and stale action items surface late.

## Input meetings

The three Orion program meetings (see [Decision reversals](decision-reversals.md) for the
timeline), involving Helena (director), Sam (staff engineer), Wei (security), and Diego
(SRE), each owning commitments across the program.

## Analysis

```bash
meeting-memory import-dir examples/organizations/enterprise --db orion.db --recursive
meeting-memory graph --db orion.db
meeting-memory insights --db orion.db
meeting-memory recommendations --db orion.db
```

The organizational graph projects people, meetings, decisions, risks, and commitments
into nodes and typed edges, while the intelligence engine evaluates commitment health
and ownership concentration.

## Output

```
[high]   (commitment) Commitment resolution rate is low (0%)
[medium] (commitment) Commitment open for 42 days
[medium] (risk)       Risk unresolved for 42 days
```

## Insights

- Commitment follow-through is the program's weakest signal: none of the tracked action
  items were marked resolved in the analysed window.
- Specific commitments (e.g. *"produce the service dependency map"*) have been open for
  the entire window, identifying concrete aging work.
- The graph makes ownership explicit — you can traverse from any engineer to the
  decisions and commitments they touch (`meeting-memory neighbors <node-id>`).

## Recommendations

> **Improve commitment follow-through.** Track commitments to completion in each
> meeting's review.

> **Review an aging commitment.** Check whether it is still relevant and set a due date.

For an engineering org, wire this into the cadence: end each meeting by reconciling open
commitments from the graph, and use the recurring-risk and aging-commitment insights as
a standing reliability checklist.
