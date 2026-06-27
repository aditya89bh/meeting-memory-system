"""Unit tests for the graph CLI subcommands: graph, neighbors, path, export-graph."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from meeting_memory.cli import _format_node_line, main
from meeting_memory.graph import EntityType, GraphNode
from meeting_memory.storage import SQLiteMemoryStore, import_meeting

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _transcript(title: str, date: str) -> str:
    return (
        f"---\ntitle: {title}\ndate: {date}\n---\n"
        "[00:00:05] Alice: We decided to build Project Atlas on Postgres.\n"
        "[00:00:20] Bob: I will deploy Postgres by Friday.\n"
        "[00:00:35] Alice: There is a risk that Project Atlas will slip.\n"
    )


def _seed(tmp_path: Path) -> Path:
    db = tmp_path / "db.sqlite"
    with SQLiteMemoryStore(db) as store:
        for name, date in [("jan", "2026-01-05"), ("feb", "2026-02-10")]:
            path = tmp_path / f"{name}.txt"
            path.write_text(_transcript(f"{name} Project Atlas", date), encoding="utf-8")
            import_meeting(path, store, now=_NOW)
    return db


def test_graph_human_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["graph", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Nodes:" in out
    assert "By node type:" in out
    assert "By relationship:" in out


def test_graph_json_and_type_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["graph", "--db", str(db), "--type", "project", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["nodes"] > 0
    assert payload["by_node_type"]["project"] == 1
    assert all(node["node_type"] == "project" for node in payload["listed"])


def test_graph_human_lists_nodes_when_filtered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _seed(tmp_path)
    assert main(["graph", "--db", str(db), "--type", "project"]) == 0
    out = capsys.readouterr().out
    assert "Nodes:" in out
    assert "project:atlas" in out


def test_neighbors_human_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["neighbors", "project:atlas", "--db", str(db), "--type", "meeting"]) == 0
    out = capsys.readouterr().out
    assert "node: project:atlas" in out
    assert "meeting:" in out


def test_neighbors_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["neighbors", "project:atlas", "--db", str(db), "--depth", "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(node["node_id"] == "project:atlas" for node in payload["nodes"])
    assert "edges" in payload


def test_path_human_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["path", "person:alice", "project:atlas", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "path (length" in out

    assert main(["path", "person:alice", "project:atlas", "--db", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["nodes"][0]["node_id"] == "person:alice"


def test_path_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["path", "person:alice", "person:ghost", "--db", str(db)]) == 0
    assert "No path found." in capsys.readouterr().out

    assert main(["path", "person:alice", "person:ghost", "--db", str(db), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) is None


def test_export_graph_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert main(["export-graph", "--db", str(db), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "nodes" in payload and "edges" in payload


def test_export_graph_mermaid_and_dot_with_filter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _seed(tmp_path)
    assert (
        main(["export-graph", "--db", str(db), "--format", "mermaid", "--type", "meeting,project"])
        == 0
    )
    assert capsys.readouterr().out.startswith("graph TD")

    assert main(["export-graph", "--db", str(db), "--format", "dot", "--limit", "5"]) == 0
    assert capsys.readouterr().out.startswith("digraph memory_graph")


def test_format_node_line_truncates_long_labels() -> None:
    node = GraphNode(
        node_id="decision:x",
        node_type=EntityType.DECISION,
        label="word " * 40,
        ref_id="x",
    )
    line = _format_node_line(node)
    assert line.startswith("decision:x  [decision]")
    assert "…" in line


def test_neighbors_relationship_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert (
        main(
            [
                "neighbors",
                "project:atlas",
                "--db",
                str(db),
                "--relationship",
                "mentions",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert all(edge["relationship"] == "mentions" for edge in payload["edges"])


def test_path_with_relationship_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed(tmp_path)
    assert (
        main(
            ["path", "person:alice", "project:atlas", "--db", str(db), "--relationship", "mentions"]
        )
        == 0
    )
    assert "path (length" in capsys.readouterr().out


def test_unknown_node_type_is_rejected(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    with pytest.raises(SystemExit):
        main(["graph", "--db", str(db), "--type", "nonsense"])


def test_unknown_relationship_is_rejected(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    with pytest.raises(SystemExit):
        main(["neighbors", "project:atlas", "--db", str(db), "--relationship", "nonsense"])


def test_empty_type_and_relationship_sets_are_rejected(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    with pytest.raises(SystemExit):
        main(["graph", "--db", str(db), "--type", ","])
    with pytest.raises(SystemExit):
        main(["neighbors", "project:atlas", "--db", str(db), "--relationship", ","])


def test_type_parser_skips_blank_entries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _seed(tmp_path)
    # A trailing comma exercises the blank-token skip branch.
    assert main(["graph", "--db", str(db), "--type", "project,", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["by_node_type"]["project"] == 1
