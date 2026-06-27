# Tutorial 1 — Getting started

This tutorial gets you from an empty machine to a complete, working demo in a couple of
minutes. No external services, API keys, or LLMs are required — everything runs locally
and deterministically.

## Prerequisites

- Python 3.11 or newer
- `pip` and a virtual environment tool (`venv` is fine)

## Install

```bash
git clone https://github.com/aditya89bh/meeting-memory-system.git
cd meeting-memory-system

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e .                 # core
# Optional extras:
pip install -e ".[api,sdk]"      # REST API + Python SDK
```

Verify the install:

```bash
meeting-memory --version
```

## Run the guided demo

The fastest way to see every subsystem working together is the built-in demo. It
imports example meetings, builds memory, searches, builds the graph, generates
intelligence, and renders a report — in well under a minute:

```bash
meeting-memory demo
```

You will see six labelled steps and a final timing line. To keep the database so you can
poke at it afterwards:

```bash
meeting-memory demo --keep
```

This writes `demo.db` in the current directory and prints the commands to explore it.

## Your first real database

Import one of the bundled [example organizations](../../examples/organizations/) and look
at what was captured:

```bash
meeting-memory import-dir examples/organizations/startup --db startup.db --recursive
meeting-memory stats --db startup.db
```

## Where to go next

- [Import meetings](import-meetings.md) — import your own transcripts.
- [Searching memory](searching-memory.md) — query what you imported.
- [Generating insights](generating-insights.md) — get an intelligence report.
