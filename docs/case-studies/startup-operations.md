# Case study — Startup operations

**Dataset:** [`examples/organizations/startup`](../../examples/organizations/startup/)

## Problem

Northwind is a small startup racing to ship the Aurora MVP. The founders move fast and
make decisions in quick syncs, but with no shared memory they lose track of who promised
what, which risks are still live, and whether the launch decision has actually stabilized.
At startup speed, a dropped commitment can sink the launch.

## Input meetings

Three founder meetings across the launch run-up:

- **2026-01-06 — Kickoff**: launch Aurora with Stripe; private beta on Feb 3; payment
  integration risk raised.
- **2026-01-20 — Planning**: payment risk raised again; decision evolves to dual-provider
  payments; load test commitment.
- **2026-02-03 — Launch Review**: payment risk mitigated; decision to go public on Mar 2;
  new support-volume risk.

## Analysis

```bash
meeting-memory import-dir examples/organizations/startup --db northwind.db --recursive
meeting-memory report --db northwind.db
```

## Output

```
[high]   (commitment) Commitment resolution rate is low (0%)
[medium] (decision)   Decision revisited across 2 meetings
[medium] (person)     Marco owns 4 open commitments
[medium] (risk)       Risk recurred in 2 meetings
```

## Insights

- One engineer (Marco) is carrying four open commitments — a classic small-team
  bottleneck that the ownership analysis flags before it becomes a blocker.
- The "February beta is the top priority" decision was revisited rather than locked,
  signalling churn in the launch plan.
- The payment-integration risk recurred across meetings before being mitigated — the
  arc the team eventually closes, but only after it surfaced twice.

## Recommendations

> **Rebalance an overloaded owner.** Redistribute or de-scope commitments to relieve the
> bottleneck.

> **Improve commitment follow-through** and **settle a repeatedly revisited decision.**

For a startup, the highest-leverage habit is a 60-second end-of-meeting review against
the open commitments and recurring risks the system surfaces — keeping the small team
honest without adding process overhead.
