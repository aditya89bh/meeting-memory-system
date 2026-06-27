"""Unit tests for the connector, automation, scheduling, and logging CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from connector_helpers import write_transcripts
from meeting_memory.cli import main


def _seed(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(db, source)`` with a populated database and a transcript dir."""
    source = write_transcripts(tmp_path / "data")
    db = tmp_path / "atlas.db"
    assert main(["import-dir", str(source), "--db", str(db)]) == 0
    return db, source


def _pipeline(tmp_path: Path, source: Path, report: Path) -> Path:
    config = tmp_path / "pipeline.yaml"
    config.write_text(
        "name: daily\n"
        "schedule:\n  frequency: daily\n"
        "steps:\n"
        f"  - type: import\n    source: {source}\n    recursive: true\n"
        "  - type: graph\n"
        "  - type: intelligence\n"
        f"  - type: export\n    format: markdown\n    output: {report}\n",
        encoding="utf-8",
    )
    return config


def test_import_dir_human(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = write_transcripts(tmp_path / "data")
    db = tmp_path / "atlas.db"
    assert main(["import-dir", str(source), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "files" in out.lower()


def test_import_dir_json_and_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = write_transcripts(tmp_path / "data")
    db = tmp_path / "atlas.db"
    assert main(["import-dir", str(source), "--db", str(db), "--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert not db.exists()


def test_import_dir_recursive(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    nested = source / "nested"
    write_transcripts(nested)
    db = tmp_path / "atlas.db"
    assert main(["import-dir", str(source), "--db", str(db), "--recursive"]) == 0


def test_export_markdown_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db, _ = _seed(tmp_path)
    assert main(["export", "--db", str(db), "--format", "markdown"]) == 0
    assert capsys.readouterr().out.strip()


def test_export_json_to_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db, _ = _seed(tmp_path)
    capsys.readouterr()
    out_file = tmp_path / "export.json"
    assert main(["export", "--db", str(db), "--format", "json", "--output", str(out_file)]) == 0
    assert out_file.exists()
    assert "destination" in capsys.readouterr().out


def test_export_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db, _ = _seed(tmp_path)
    capsys.readouterr()
    assert main(["export", "--db", str(db), "--format", "markdown", "--dry-run", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True


def test_automate_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = write_transcripts(tmp_path / "data")
    report = tmp_path / "report.md"
    config = _pipeline(tmp_path, source, report)
    db = tmp_path / "atlas.db"
    assert main(["automate", str(config), "--db", str(db)]) == 0
    assert report.exists()
    assert "import" in capsys.readouterr().out


def test_automate_dry_run(tmp_path: Path) -> None:
    source = write_transcripts(tmp_path / "data")
    report = tmp_path / "report.md"
    config = _pipeline(tmp_path, source, report)
    db = tmp_path / "atlas.db"
    assert main(["automate", str(config), "--db", str(db), "--dry-run"]) == 0
    assert not report.exists()


def test_automate_failure_exit_code(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text(
        "name: bad\nsteps:\n  - type: import\n    source: missing-directory\n",
        encoding="utf-8",
    )
    db = tmp_path / "atlas.db"
    assert main(["automate", str(config), "--db", str(db)]) == 1


def test_jobs_empty_and_populated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "atlas.db"
    assert main(["jobs", "--db", str(db)]) == 0
    assert "No automation runs" in capsys.readouterr().out
    source = write_transcripts(tmp_path / "data")
    config = _pipeline(tmp_path, source, tmp_path / "r.md")
    assert main(["automate", str(config), "--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["jobs", "--db", str(db), "--json"]) == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == 1
    assert records[0]["job"] == "daily"


def test_schedule_daily_and_manual(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = write_transcripts(tmp_path / "data")
    config = _pipeline(tmp_path, source, tmp_path / "r.md")
    assert main(["schedule", str(config), "--after", "2026-06-27T14:30:00", "--count", "3"]) == 0
    out = capsys.readouterr().out
    assert "frequency: daily" in out
    assert out.count("2026-06") >= 1
    assert main(["schedule", str(config), "--json", "--count", "2"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["runs"]) == 2


def test_logs_empty_and_populated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "atlas.db"
    assert main(["logs", "--db", str(db)]) == 0
    assert "No logs recorded" in capsys.readouterr().out
    source = write_transcripts(tmp_path / "data")
    config = _pipeline(tmp_path, source, tmp_path / "r.md")
    assert main(["automate", str(config), "--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["logs", "--db", str(db), "--json"]) == 0
    records = json.loads(capsys.readouterr().out)
    assert records
    correlation = records[0]["correlation_id"]
    assert main(["logs", "--db", str(db), "--correlation", correlation, "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert correlation in out
