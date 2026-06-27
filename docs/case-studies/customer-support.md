# Case study — Customer support

**Dataset:** [`examples/organizations/saas`](../../examples/organizations/saas/)

## Problem

Lumen's customer success function needs to act on churn signals before renewals, but the
relevant context — who flagged a churn driver, which health-scoring work was promised,
whether at-risk accounts were followed up — is spread across leadership and engineering
meetings. Support and success teams react late because nobody is tracking these threads
to closure.

## Input meetings

The three Insights Platform meetings, viewed through a customer-success lens:

- **2026-01-08 — Growth Review**: identify top churn drivers before the renewal cycle;
  customer health scoring is still pending and needs an owner.
- **2026-01-29 — Scaling Sync**: an SLA commitment is requested before the enterprise
  pilot signs.
- **2026-02-19 — Pilot Retro**: customer health scoring goes live and flags two at-risk
  accounts early; SLA rolled into enterprise contracts; success-team hiring planned.

## Analysis

```bash
meeting-memory import-dir examples/organizations/saas --db lumen.db --recursive
meeting-memory search "customer health" --db lumen.db
meeting-memory insights --db lumen.db
```

Search pulls every customer-facing commitment and question into one view, while the
commitment-health analysis shows whether those promises were kept.

## Output

```
[high]   (commitment) Commitment resolution rate is low (0%)
[medium] (commitment) Commitment open for 42 days
[medium] (person)     Omar owns 3 open commitments
```

## Insights

- Customer-facing commitments (health scoring, SLA, success hiring) were tracked across
  meetings, so it is clear which were delivered (health scoring) and which lingered.
- The "identify churn drivers" question and the "health scoring" commitment are linked in
  memory, turning a vague concern into a trackable thread that ends with two at-risk
  accounts flagged early.
- Ownership concentration (Omar) shows where customer-success follow-through is at risk
  of stalling.

## Recommendations

> **Improve commitment follow-through** and **review an aging commitment.**

For a support/success org, run retrieval on customer-centric terms (*health*, *churn*,
*SLA*) before each renewal cycle and reconcile the resulting commitments — so the early
warning the system surfaces actually reaches the customer in time.
