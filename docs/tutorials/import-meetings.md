# Tutorial 2 — Import meetings

Importing is how raw transcripts become structured, queryable memory. This tutorial
covers single files, whole directories, supported formats, and idempotent re-imports.

## Transcript format

A transcript is a plain-text file with optional front matter followed by timestamped
utterances:

```text
---
title: Project Atlas Kickoff
date: 2026-02-02
team: Platform
---
[00:00:05] Priya: We decided to build Atlas on PostgreSQL for the first release.
[00:00:40] Marco: I will set up the staging environment by next Friday.
[00:01:00] Marco: There is a risk that the vendor API rate limits will slow ingestion.
```

The extractor recognises natural cues — *"We decided…"* (decision), *"I will…"*
(commitment), *"There is a risk…"* (risk), *"Can we…?"* (question), *"Assuming…"*
(assumption), and *"still pending"* (open loop).

JSON, Markdown, and CSV transcripts are also supported.

## Import a single file

```bash
meeting-memory import examples/history/meeting1.txt --db atlas.db
```

The summary lists how many memories of each type were stored.

## Import a directory

```bash
meeting-memory import-dir examples/organizations/saas --db lumen.db --recursive
```

Useful options:

- `--recursive` — descend into subdirectories.
- `--pattern '*.txt'` — only import matching files.
- `--limit N` — stop after N files.
- `--dry-run` — show what would be imported without writing.

## Control extraction

```bash
# Only extract decisions and risks
meeting-memory import meeting.txt --db atlas.db --types decision,risk

# Drop low-confidence extractions
meeting-memory import meeting.txt --db atlas.db --min-confidence 0.5
```

## Idempotent re-imports

Each meeting is keyed by a transcript hash, so importing the same file twice does not
create duplicates. Edit the transcript and re-import to update it.

## Inspect what was stored

```bash
meeting-memory meetings --db atlas.db        # list meetings
meeting-memory stats --db atlas.db           # counts by type and status
meeting-memory show <meeting-id> --db atlas.db
```

Next: [Searching memory](searching-memory.md).
