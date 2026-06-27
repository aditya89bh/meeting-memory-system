"""Tests for the Phase 9 operations CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meeting_memory.cli import main
from ops_helpers import build_db


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return build_db(tmp_path)


# -- benchmark ----------------------------------------------------------------


def test_benchmark_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["benchmark", "--dataset", "small", "--iterations", "1"]) == 0
    out = capsys.readouterr().out
    assert "Benchmark report: small" in out


def test_benchmark_json_to_file(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    assert main(["benchmark", "--dataset", "small", "--json", "-o", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["dataset"] == "small"


def test_benchmark_rejects_zero_iterations() -> None:
    with pytest.raises(SystemExit):
        main(["benchmark", "--iterations", "0"])


# -- replay -------------------------------------------------------------------


def test_replay_default(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["replay", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Replay: all meetings" in out
    assert "decision:" in out


def test_replay_timeline_json(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["replay", "--db", str(db), "--timeline", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["meeting_count"] == 6


def test_replay_timeline_text(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["replay", "--db", str(db), "--timeline", "--project", "Atlas"]) == 0
    assert "Timeline: project=Atlas" in capsys.readouterr().out


def test_replay_json_result(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["replay", "--db", str(db), "--json", "--person", "Priya"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "steps_played" in payload


def test_replay_to_file(db: Path, tmp_path: Path) -> None:
    out = tmp_path / "replay.txt"
    assert main(["replay", "--db", str(db), "-o", str(out)]) == 0
    assert "Replay:" in out.read_text()


# -- metrics ------------------------------------------------------------------


def test_metrics_text(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["metrics", "--db", str(db)]) == 0
    assert "Overall health" in capsys.readouterr().out


def test_metrics_json(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["metrics", "--db", str(db), "--json"]) == 0
    assert "overall" in capsys.readouterr().out


def test_metrics_json_to_file(db: Path, tmp_path: Path) -> None:
    out = tmp_path / "m.json"
    assert main(["metrics", "--db", str(db), "--format", "json", "-o", str(out)]) == 0
    assert "overall" in out.read_text()


def test_metrics_prometheus(db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["metrics", "--db", str(db), "--format", "prometheus"]) == 0
    out = capsys.readouterr().out
    assert "meeting_memory_health_overall" in out
    assert "meeting_memory_meetings_total" in out


def test_metrics_prometheus_to_file(db: Path, tmp_path: Path) -> None:
    out = tmp_path / "m.prom"
    assert main(["metrics", "--db", str(db), "--format", "prometheus", "-o", str(out)]) == 0
    assert "meeting_memory_memories_total" in out.read_text()


# -- backup / restore ---------------------------------------------------------


def test_backup_physical_and_restore(
    db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "copy.db"
    assert main(["backup", "--db", str(db), "-o", str(backup)]) == 0
    assert "Backed up" in capsys.readouterr().out

    restored = tmp_path / "restored.db"
    assert main(["restore", "--db", str(restored), str(backup)]) == 0
    assert "Restored: ok=True" in capsys.readouterr().out


def test_backup_json(db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    backup = tmp_path / "copy.db"
    assert main(["backup", "--db", str(db), "-o", str(backup), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["meetings"] == 6


def test_snapshot_backup_and_restore(
    db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snap = tmp_path / "snap.json"
    assert main(["backup", "--db", str(db), "-o", str(snap), "--snapshot"]) == 0
    assert "Wrote snapshot" in capsys.readouterr().out

    rebuilt = tmp_path / "rebuilt.db"
    assert main(["restore", "--db", str(rebuilt), str(snap), "--snapshot"]) == 0
    assert "Restored: ok=True" in capsys.readouterr().out


def test_snapshot_backup_json(db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    snap = tmp_path / "snap.json"
    assert main(["backup", "--db", str(db), "-o", str(snap), "--snapshot", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["type"] == "snapshot"


def test_restore_json_and_no_verify(
    db: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "copy.db"
    main(["backup", "--db", str(db), "-o", str(backup)])
    capsys.readouterr()
    restored = tmp_path / "restored.db"
    assert main(["restore", "--db", str(restored), str(backup), "--no-verify", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True


# -- profile ------------------------------------------------------------------


@pytest.mark.parametrize("operation", ["search", "graph", "intelligence", "report"])
def test_profile_operations(db: Path, operation: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["profile", "--db", str(db), "--operation", operation, "--top", "3"]) == 0
    assert f"Profile: {operation}" in capsys.readouterr().out


def test_profile_import(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["profile", "--operation", "import", "--dataset", "small", "--top", "2"]) == 0
    assert "Profile: import" in capsys.readouterr().out


def test_profile_json_to_file(db: Path, tmp_path: Path) -> None:
    out = tmp_path / "profile.json"
    assert main(["profile", "--db", str(db), "--operation", "graph", "--json", "-o", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["operation"] == "graph"


def test_profile_rejects_zero_top() -> None:
    with pytest.raises(SystemExit):
        main(["profile", "--top", "0"])
