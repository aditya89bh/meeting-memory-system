# Case studies

Realistic, reproducible studies that show the Meeting Memory System turning a stack of
meeting transcripts into actionable institutional knowledge. Every study is backed by a
bundled [example organization](../../examples/organizations/), so you can reproduce the
analysis yourself with the commands shown.

| Case study | Scenario | Dataset |
|---|---|---|
| [Recurring project risks](recurring-project-risks.md) | A reliability risk keeps resurfacing unaddressed | `saas` |
| [Decision reversals](decision-reversals.md) | A migration plan changes direction three times | `enterprise` |
| [Knowledge reuse](knowledge-reuse.md) | Reproducibility practices captured and reused | `research-lab` |
| [Engineering organization](engineering-organization.md) | Ownership, on-call, and reliability at scale | `enterprise` |
| [Startup operations](startup-operations.md) | An MVP launch tracked end to end | `startup` |
| [Customer support](customer-support.md) | Churn signals and customer health follow-through | `saas` |

Each study follows the same structure: **Problem → Input meetings → Analysis → Output →
Insights → Recommendations**.

## Reproducing a study

```bash
meeting-memory import-dir examples/organizations/<dataset> --db study.db --recursive
meeting-memory report --db study.db
```
