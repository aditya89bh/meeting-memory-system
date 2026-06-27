# Example organizations

Five self-contained, deterministic meeting datasets that model how different kinds
of organizations accumulate institutional memory over a quarter. Each dataset is a
folder of plain-text transcripts in the standard Meeting Memory format and is safe
to import into a throwaway database.

| Organization | Folder | Scenario |
|---|---|---|
| Small Startup | [`startup/`](startup/) | Northwind ships the **Aurora MVP**: payments choice, launch readiness, and a public-launch decision. |
| Growing SaaS Company | [`saas/`](saas/) | Lumen scales its **Insights Platform**: database migration, reliability SLAs, and customer success hiring. |
| Enterprise Engineering | [`enterprise/`](enterprise/) | Orion runs a phased **cloud migration** under compliance and reliability constraints. |
| Research Lab | [`research-lab/`](research-lab/) | Helix Bio Lab runs a **protein folding study** with reproducibility and reagent-supply concerns. |
| University | [`university/`](university/) | Westbridge redesigns a **data science program** under accreditation and enrollment pressure. |

## What each dataset demonstrates

Every organization is authored so the intelligence layer has something concrete to find:

- **Decision evolution** — a single decision is revisited across the three meetings
  (e.g. Orion's migration plan moves from *lift-and-shift → containers → managed Kubernetes*).
- **Recurring risks** — the same risk reappears in consecutive meetings before being
  marked mitigated (e.g. Lumen's query-latency risk, Westbridge's enrollment risk).
- **Commitments** — explicit `I will …` action items with owners and due dates.
- **Organizational graph** — multiple people, a named project, and cross-meeting links.
- **Reports** — enough signal to render a non-trivial intelligence report.

## Try one

```bash
# Import an organization into a temporary database
meeting-memory import-dir examples/organizations/enterprise --db /tmp/orion.db --recursive

# See what was captured
meeting-memory stats --db /tmp/orion.db

# Trace how the migration decision evolved
meeting-memory search "migrate core services" --db /tmp/orion.db

# Generate the intelligence report
meeting-memory report --db /tmp/orion.db
```

Or skip the setup entirely and run the guided tour:

```bash
meeting-memory demo
```
