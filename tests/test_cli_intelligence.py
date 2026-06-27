"""Tests for the intelligence CLI subcommands."""

from __future__ import annotations

import argparse
import json

import pytest

from intelligence_helpers import make_meeting, make_memory
from meeting_memory.cli import _parse_insight_types, _parse_meeting_ids, main
from meeting_memory.storage import SQLiteMemoryStore


def _seed(db_path: str) -> None:
    meetings = [
        make_meeting("m1", date="2026-01-01", title="Project Atlas Kickoff"),
        make_meeting("m2", date="2026-02-15", title="Project Atlas Review"),
        make_meeting("m3", date="2026-03-20", title="Project Atlas Sync"),
    ]
    memories = [
        make_memory(
            "r1",
            "risk",
            "Project Atlas may slip the deadline",
            meeting_id="m1",
            created_at="2026-01-01T09:00:00+00:00",
            content_hash="atlas",
        ),
        make_memory(
            "r2",
            "risk",
            "Project Atlas may slip the deadline",
            meeting_id="m2",
            created_at="2026-02-15T09:00:00+00:00",
            content_hash="atlas",
        ),
        make_memory(
            "r3",
            "risk",
            "Project Atlas may slip the deadline",
            meeting_id="m3",
            created_at="2026-03-20T09:00:00+00:00",
            content_hash="atlas",
        ),
        make_memory(
            "c1",
            "commitment",
            "Alice finalizes the spec",
            meeting_id="m1",
            created_at="2026-01-01T09:02:00+00:00",
            metadata={"owner": "Alice", "due": "2026-01-15"},
        ),
        make_memory(
            "c2",
            "commitment",
            "Alice sets up CI",
            meeting_id="m1",
            created_at="2026-01-01T09:03:00+00:00",
            metadata={"owner": "Alice"},
        ),
        make_memory(
            "c3",
            "commitment",
            "Alice writes tests",
            meeting_id="m2",
            created_at="2026-02-15T09:03:00+00:00",
            metadata={"owner": "Alice"},
        ),
    ]
    store = SQLiteMemoryStore(db_path)
    for meeting in meetings:
        store.save_meeting(meeting)
    store.save_many(memories)
    store.close()


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "phase6.db"
    _seed(str(path))
    return str(path)


# -- argument parsers ---------------------------------------------------------


def test_parse_insight_types() -> None:
    parsed = _parse_insight_types("recurring_risk, overdue_commitment")
    assert {t.value for t in parsed} == {"recurring_risk", "overdue_commitment"}


def test_parse_insight_types_skips_blank_and_rejects_unknown() -> None:
    assert {t.value for t in _parse_insight_types("recurring_risk,")} == {"recurring_risk"}
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_insight_types("nope")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_insight_types(" , ")


def test_parse_meeting_ids() -> None:
    assert _parse_meeting_ids("m1, m2") == frozenset({"m1", "m2"})
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_meeting_ids("  ,  ")


# -- insights -----------------------------------------------------------------


def test_insights_human_and_json(db, capsys) -> None:
    assert main(["insights", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "recurring" in out.lower() or "risk" in out.lower()

    assert main(["insights", "--db", db, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert any(item["type"] == "recurring_risk" for item in payload)


def test_insights_type_and_limit_filters(db, capsys) -> None:
    assert main(["insights", "--db", db, "--type", "recurring_risk", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {item["type"] for item in payload} == {"recurring_risk"}

    assert main(["insights", "--db", db, "--limit", "1", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1


def test_insights_empty(tmp_path, capsys) -> None:
    path = tmp_path / "empty.db"
    store = SQLiteMemoryStore(str(path))
    store.save_meeting(make_meeting("m1", date="2026-01-01"))
    store.close()
    assert main(["insights", "--db", str(path)]) == 0
    assert "No insights found." in capsys.readouterr().out


def test_insights_person_filter(db, capsys) -> None:
    assert main(["insights", "--db", db, "--person", "Alice", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(item["category"] == "person" for item in payload)


# -- metrics ------------------------------------------------------------------


def test_metrics_human_and_json(db, capsys) -> None:
    assert main(["metrics", "--db", db]) == 0
    assert "Overall health" in capsys.readouterr().out

    assert main(["metrics", "--db", db, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "overall" in payload
    assert payload["risk"]["total"] == 3


# -- recommendations ----------------------------------------------------------


def test_recommendations_human_json_limit(db, capsys) -> None:
    assert main(["recommendations", "--db", db]) == 0
    assert "Follow up" in capsys.readouterr().out or "Rebalance" in capsys.readouterr().out

    assert main(["recommendations", "--db", db, "--json", "--limit", "1"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1


def test_recommendations_empty(tmp_path, capsys) -> None:
    path = tmp_path / "empty2.db"
    store = SQLiteMemoryStore(str(path))
    store.save_meeting(make_meeting("m1", date="2026-01-01"))
    store.close()
    assert main(["recommendations", "--db", str(path)]) == 0
    assert "No recommendations." in capsys.readouterr().out


# -- report -------------------------------------------------------------------


def test_report_formats_stdout(db, capsys) -> None:
    assert main(["report", "--db", db]) == 0
    assert "ORGANIZATIONAL INTELLIGENCE REPORT" in capsys.readouterr().out

    assert main(["report", "--db", db, "--format", "markdown"]) == 0
    assert "# Organizational Intelligence Report" in capsys.readouterr().out

    assert main(["report", "--db", db, "--format", "json"]) == 0
    assert "overall" in json.loads(capsys.readouterr().out)["health"]


def test_report_writes_output_file(db, tmp_path, capsys) -> None:
    out_file = tmp_path / "report.md"
    assert main(["report", "--db", db, "--format", "markdown", "--output", str(out_file)]) == 0
    assert "Wrote report to" in capsys.readouterr().out
    assert out_file.read_text(encoding="utf-8").startswith("# Organizational")


def test_report_unknown_format_rejected(db) -> None:
    with pytest.raises(SystemExit):
        main(["report", "--db", db, "--format", "pdf"])
