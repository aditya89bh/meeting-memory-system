# Tutorial 8 — Python SDK

`meeting_memory.sdk.MeetingMemoryClient` is a single client with one method per
capability and two interchangeable transports:

- **local mode** — in-process, bound directly to a SQLite database. No server, no
  network. Great for scripts and notebooks.
- **HTTP mode** — talks to a running API server. Same method surface, same behaviour.

## Install

```bash
pip install -e ".[sdk]"
```

## Create a client

```python
from meeting_memory.sdk import MeetingMemoryClient

# Local (in-process) mode
with MeetingMemoryClient.local("atlas.db") as client:
    print(client.health())

# HTTP mode (requires a running server)
with MeetingMemoryClient.connect("http://127.0.0.1:8000") as client:
    print(client.health())
```

`client.mode` is `"local"` or `"http"`. Because both transports go through the same
request path, you can develop against local mode and deploy against HTTP mode without
changing a line of logic.

## A complete workflow

```python
from meeting_memory.sdk import MeetingMemoryClient

with MeetingMemoryClient.local("atlas.db") as client:
    # Import a directory of transcripts
    client.import_directory("examples/organizations/saas", recursive=True)

    # Inspect what was stored
    stats = client.stats()
    print("meetings:", stats["meetings"], "memories:", stats["memories"])

    # Ranked retrieval
    for hit in client.search("reliability", limit=3)["results"]:
        print(round(hit["score"], 3), hit["memory"]["text"])

    # Graph exploration
    summary = client.graph()
    print("nodes:", summary["nodes"], "edges:", summary["edges"])

    # Intelligence (report() returns {"format": ..., "content": ...})
    report = client.report(fmt="markdown")
    print(report["content"][:200])
```

## Method reference

| Method | Purpose |
|---|---|
| `health()`, `version()` | Liveness and version |
| `import_file(path, fmt=None, ...)` | Import a single transcript |
| `import_directory(path, recursive=True, ...)` | Import a directory |
| `meetings(...)`, `get_meeting(id)`, `stats()` | Browse meetings |
| `memories(...)`, `get_memory(id)` | Browse memories |
| `search(q, ...)` | Ranked retrieval |
| `graph(...)`, `neighbors(...)`, `path(...)` | Graph queries |
| `insights(...)`, `metrics(...)`, `recommendations(...)`, `report(fmt=...)` | Intelligence |
| `run_pipeline(...)`, `jobs(...)`, `logs(...)` | Automation |

See [`notebooks/05_sdk.ipynb`](../../notebooks/05_sdk.ipynb) for a runnable version of
this tutorial.

Next: [Docker deployment](docker-deployment.md).
