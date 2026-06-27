# Python SDK

`meeting_memory.sdk.MeetingMemoryClient` is a single client with one method per
capability and two interchangeable transports that share the exact same method
surface:

- **local mode** — an in-process transport bound to a SQLite database. Calls run
  through the real FastAPI routers and the shared service layer with no network
  and no running server.
- **HTTP mode** — a real HTTP client talking to a running API server.

Because both modes go through the same request path, switching between them never
changes behaviour.

## Installation

```bash
pip install -e ".[sdk]"   # httpx for the client
```

## Creating a client

```python
from meeting_memory.sdk import MeetingMemoryClient

# Local (in-process) mode
client = MeetingMemoryClient.local("atlas.db")

# HTTP mode
client = MeetingMemoryClient.connect("http://127.0.0.1:8000")

# Both support the context-manager protocol
with MeetingMemoryClient.local("atlas.db") as client:
    ...
```

`client.mode` is `"local"` or `"http"`. Pass exactly one of `db=` or
`base_url=` to the constructor (`MeetingMemoryClient(db=...)` /
`MeetingMemoryClient(base_url=...)`); providing both or neither raises
`ValueError`.

## Methods

| Method | Maps to |
| --- | --- |
| `health()`, `version()` | `GET /health`, `GET /version` |
| `import_file(path, fmt=None, ...)` | `POST /meetings/import` (uploads file content) |
| `import_directory(path, recursive=True, ...)` | `POST /meetings/import` (server-side path) |
| `meetings(limit=, offset=)` | `GET /meetings` |
| `get_meeting(id)` | `GET /meetings/{id}` |
| `stats()` | `GET /meetings/stats` |
| `memories(...)` | `GET /memories` |
| `get_memory(id)` | `GET /memories/{id}` |
| `search(q, ...)` | `GET /search` |
| `graph(node_type=, limit=)` | `GET /graph` |
| `neighbors(node_id, depth=, ...)` | `GET /graph/neighbors` |
| `path(source, target, depth=, ...)` | `GET /graph/path` |
| `insights(...)`, `metrics(...)`, `recommendations(...)`, `report(fmt=...)` | intelligence endpoints |
| `run_pipeline(config=/pipeline=, dry_run=)` | `POST /automation/run` |
| `jobs(...)`, `logs(...)` | `GET /automation/jobs`, `GET /automation/logs` |

Every method returns the decoded JSON body as a plain `dict` (identical in both
modes). The low-level `client.request(method, path, params=, json=)` is available
for endpoints not yet wrapped.

## End-to-end example (local mode)

```python
from meeting_memory.sdk import MeetingMemoryClient

with MeetingMemoryClient.local("atlas.db") as client:
    client.import_directory("examples/history", recursive=True)

    hits = client.search("postgres")
    for item in hits["results"]:
        print(item["score"], item["memory"]["text"])

    print("health:", client.metrics()["overall"])
    print(client.report(fmt="markdown")["content"])

    run = client.run_pipeline(
        pipeline={"name": "nightly", "steps": [{"type": "graph"}, {"type": "intelligence"}]}
    )
    print(run["status"])
```

The runnable version lives at [`examples/api/sdk_quickstart.py`](../examples/api/sdk_quickstart.py).

## HTTP mode example

```python
from meeting_memory.sdk import MeetingMemoryClient

with MeetingMemoryClient.connect("http://127.0.0.1:8000") as client:
    print(client.health())
    print(client.search("postgres")["stats"]["returned"])
```

See [`examples/api/sdk_http.py`](../examples/api/sdk_http.py) (start a server with
`examples/api/serve.py` first).

## Error handling

Any non-2xx response raises `meeting_memory.sdk.APIError`, which preserves the
structured error payload:

```python
from meeting_memory.sdk import APIError, MeetingMemoryClient

with MeetingMemoryClient.local("atlas.db") as client:
    try:
        client.get_memory("missing")
    except APIError as exc:
        print(exc.status_code)      # 404
        print(exc.error)            # "MemoryNotFoundError"
        print(exc.detail)           # human-readable message
        print(exc.correlation_id)   # correlation id, when present
```

## Notes on import semantics

- `import_file` reads the file and uploads its **content** with a format inferred
  from the suffix (`.txt`/`.json`/`.md`/`.csv`), so it works even when the client
  and server are different machines.
- `import_directory` sends a **server-side path** (a directory or `.zip`) and is
  resolved relative to the server's working directory. In local mode the client
  and server are the same process.
