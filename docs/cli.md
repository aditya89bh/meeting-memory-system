# CLI reference

Every capability is available through the `meeting-memory` command. Run
`meeting-memory <command> --help` for the full, authoritative options of any command.
Most commands accept `--db PATH` (default: `meeting-memory.db`) and `--json`.

```bash
meeting-memory --version
meeting-memory <command> --help
```

## Pipeline

| Command | Description |
|---|---|
| `parse` | Parse a transcript file and emit structured JSON. |
| `extract` | Extract structured memory records from a transcript. |
| `import` | Import a single transcript into the persistent memory store. |
| `import-dir` | Import every supported transcript in a directory (`--recursive`, `--pattern`, `--limit`, `--dry-run`). |

## Browse stored memory

| Command | Description |
|---|---|
| `list` | List stored memories, optionally filtered. |
| `show` | Show a single memory by id. |
| `meetings` | List meetings in the registry. |
| `stats` | Show aggregate statistics for the store. |

## Retrieval

| Command | Description |
|---|---|
| `search` | Search organizational memory across meetings (`--type`, `--speaker`, `--limit`, date filters). |
| `timeline` | Show matching memories in chronological order. |
| `explain` | Explain why a memory matched and show its context. |

## Graph

| Command | Description |
|---|---|
| `graph` | Build and summarise the organizational memory graph. |
| `neighbors` | Show the neighbourhood of a graph node (`--depth`). |
| `path` | Find the shortest path between two graph nodes. |
| `export-graph` | Export the graph (`--format json\|mermaid\|dot`). |

## Intelligence

| Command | Description |
|---|---|
| `insights` | Discover organizational insights across meetings. |
| `metrics` | Compute organizational-health metrics (`--format text\|json\|prometheus`). |
| `recommendations` | Generate evidence-backed recommendations. |
| `report` | Generate a full intelligence report (`--format`, `-o`, `--project`, `--person`). |

## Automation

| Command | Description |
|---|---|
| `export` | Export organizational data to a destination. |
| `automate` | Run a declarative pipeline (YAML or JSON). |
| `jobs` | List recorded automation runs. |
| `schedule` | Show upcoming run times for a pipeline schedule. |
| `logs` | Show structured connector/automation logs. |

## Operations

| Command | Description |
|---|---|
| `benchmark` | Run reproducible performance benchmarks (`--dataset`, `--iterations`, `--charts DIR`). |
| `replay` | Replay stored meetings in chronological order. |
| `backup` | Back up the database (`-o`, `--snapshot`). |
| `restore` | Restore the database from a backup or snapshot. |
| `profile` | Profile CPU and memory for a core operation. |
| `demo` | Run a guided, end-to-end demonstration (`--dataset`, `--keep`). |

## Examples

```bash
# Guided tour
meeting-memory demo

# Import an example organization and analyse it
meeting-memory import-dir examples/organizations/saas --db lumen.db --recursive
meeting-memory report --db lumen.db

# Search and explore
meeting-memory search "risk" --db lumen.db --limit 5
meeting-memory graph --db lumen.db

# Operations
meeting-memory benchmark --dataset medium
meeting-memory backup --db lumen.db -o lumen-backup.db
```
