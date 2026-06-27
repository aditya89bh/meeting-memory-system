#!/usr/bin/env python3
"""End-to-end Python SDK workflow in local (in-process) mode.

Run from the repository root::

    python examples/api/sdk_quickstart.py

This imports the bundled example transcripts into a throwaway database, then
exercises search, the knowledge graph, decision intelligence, reporting, and an
automation pipeline -- all through the same service layer the REST API uses.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from meeting_memory.sdk import MeetingMemoryClient

HISTORY = Path(__file__).resolve().parents[2] / "examples" / "history"


def main() -> None:
    """Run the end-to-end SDK workflow against a temporary database."""
    with tempfile.TemporaryDirectory(prefix="mm-sdk-") as tmp:
        db = Path(tmp) / "atlas.db"
        with MeetingMemoryClient.local(db) as client:
            print(f"mode: {client.mode}")
            print(f"version: {client.version()['version']}")

            imported = client.import_directory(HISTORY, recursive=True)
            print(
                f"imported: {imported['meetings_imported']} meeting(s), "
                f"{imported['memories_stored']} memory(ies)"
            )

            stats = client.stats()
            print(f"store: {stats['meetings']} meetings, {stats['memories']} memories")

            hits = client.search("postgres")
            print(f"search 'postgres': {hits['stats']['returned']} result(s)")
            for item in hits["results"][:3]:
                memory = item["memory"]
                print(f"  [{item['score']:.3f}] {memory['memory_type']}: {memory['text']}")

            graph = client.graph()
            print(f"graph: {graph['nodes']} nodes, {graph['edges']} edges")

            metrics = client.metrics()
            print(f"organizational health: {metrics['overall']:.2f}")

            insights = client.insights()
            print(f"insights: {insights['pagination']['total']}")
            for insight in insights["items"][:3]:
                print(f"  [{insight['severity']}] {insight['title']}")

            recommendations = client.recommendations()
            print(f"recommendations: {recommendations['pagination']['total']}")

            run = client.run_pipeline(
                pipeline={
                    "name": "quickstart",
                    "steps": [{"type": "graph"}, {"type": "intelligence"}],
                }
            )
            stages = ", ".join(stage["stage"] for stage in run["stages"])
            print(f"pipeline '{run['job']}': {run['status']} ({stages})")

            report = client.report(fmt="markdown")
            first_line = report["content"].splitlines()[0] if report["content"] else ""
            print(f"report ({report['format']}): {first_line}")


if __name__ == "__main__":
    main()
