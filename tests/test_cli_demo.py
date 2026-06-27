"""Tests for the guided ``demo`` CLI command (Phase 10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_memory.cli import main


def test_demo_ephemeral(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "guided demo" in out
    assert "[1/6] Import example meetings" in out
    assert "[6/6] Render a report" in out
    assert "Demo complete" in out
    assert "--keep" in out


def test_demo_with_persistent_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "demo.db"
    assert main(["demo", "--db", str(db), "--query", "risk"]) == 0
    out = capsys.readouterr().out
    assert db.exists()
    assert "Serve the API" in out
    assert "/dashboard" in out


def test_demo_keep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["demo", "--keep"]) == 0
    out = capsys.readouterr().out
    assert (tmp_path / "demo.db").exists()
    assert "Serve the API" in out
