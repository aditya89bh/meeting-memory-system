"""Tests for the YAML-subset parser and pipeline configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_memory.connectors import (
    ScheduleFrequency,
    build_job,
    load_pipeline,
    parse_yaml,
    validate_job,
)
from meeting_memory.connectors.config import load_config_data
from meeting_memory.exceptions import PipelineConfigError

YAML_DOC = """
# a pipeline
name: daily
enabled: true
schedule:
  frequency: daily
steps:
  - type: import
    source: examples/history
    recursive: true
    limit: 5
  - type: graph
  - type: export
    format: markdown
    output: report.md
"""


def test_parse_yaml_structures() -> None:
    data = parse_yaml(YAML_DOC)
    assert isinstance(data, dict)
    assert data["name"] == "daily"
    assert data["enabled"] is True
    assert data["schedule"] == {"frequency": "daily"}
    assert data["steps"][0]["recursive"] is True
    assert data["steps"][0]["limit"] == 5


def test_parse_yaml_scalars_and_quotes() -> None:
    data = parse_yaml('a: "quoted"\nb: 3\nc: 1.5\nd: false\ne: null\nf: plain # trailing comment\n')
    assert data == {
        "a": "quoted",
        "b": 3,
        "c": 1.5,
        "d": False,
        "e": None,
        "f": "plain",
    }


def test_parse_yaml_empty_is_none() -> None:
    assert parse_yaml("\n# only comments\n") is None


def test_parse_yaml_rejects_tabs() -> None:
    with pytest.raises(PipelineConfigError):
        parse_yaml("name: x\n\tbad: y")


def test_parse_yaml_requires_colon() -> None:
    with pytest.raises(PipelineConfigError):
        parse_yaml("just a line without a colon")


def test_parse_yaml_top_level_sequence() -> None:
    assert parse_yaml("- a\n- b\n") == ["a", "b"]


def test_build_job_from_yaml() -> None:
    job = build_job(parse_yaml(YAML_DOC))  # type: ignore[arg-type]
    assert job.name == "daily"
    assert job.schedule.frequency is ScheduleFrequency.DAILY
    assert len(job.steps) == 3
    assert job.steps[0].params["source"] == "examples/history"


def test_build_job_schedule_as_string() -> None:
    job = build_job({"name": "x", "schedule": "hourly", "steps": [{"type": "graph"}]})
    assert job.schedule.frequency is ScheduleFrequency.HOURLY


def test_build_job_cron_schedule() -> None:
    job = build_job(
        {
            "name": "x",
            "schedule": {"frequency": "cron", "cron": "0 9 * * 1"},
            "steps": [{"type": "graph"}],
        }
    )
    assert job.schedule.expression == "0 9 * * 1"


def test_build_job_unknown_frequency() -> None:
    with pytest.raises(PipelineConfigError):
        build_job({"name": "x", "schedule": "yearly", "steps": []})


def test_build_job_invalid_schedule_type() -> None:
    with pytest.raises(PipelineConfigError):
        build_job({"name": "x", "schedule": 5, "steps": []})


def test_build_job_bad_steps() -> None:
    with pytest.raises(PipelineConfigError):
        build_job({"name": "x", "steps": "notalist"})
    with pytest.raises(PipelineConfigError):
        build_job({"name": "x", "steps": ["notamapping"]})
    with pytest.raises(PipelineConfigError):
        build_job({"name": "x", "steps": [{"source": "x"}]})


def test_validate_job_problems() -> None:
    job = build_job(
        {
            "name": "",
            "steps": [
                {"type": "bogus"},
                {"type": "import"},
                {"type": "export"},
            ],
        }
    )
    problems = validate_job(job)
    assert any("name must not be empty" in p for p in problems)
    assert any("unknown type" in p for p in problems)
    assert any("requires 'source'" in p for p in problems)
    assert any("requires 'format'" in p for p in problems)


def test_validate_job_cron_problems() -> None:
    missing = build_job(
        {"name": "x", "schedule": {"frequency": "cron"}, "steps": [{"type": "graph"}]}
    )
    assert any("requires an 'expression'" in p for p in validate_job(missing))
    invalid = build_job(
        {
            "name": "x",
            "schedule": {"frequency": "cron", "expression": "bad"},
            "steps": [{"type": "graph"}],
        }
    )
    assert any("invalid cron" in p for p in validate_job(invalid))


def test_validate_job_valid() -> None:
    job = build_job(parse_yaml(YAML_DOC))  # type: ignore[arg-type]
    assert validate_job(job) == []


def test_load_config_data_json(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text('{"name": "j", "steps": [{"type": "graph"}]}', encoding="utf-8")
    data = load_config_data(path)
    assert data["name"] == "j"


def test_load_config_data_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(PipelineConfigError):
        load_config_data(path)


def test_load_config_data_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(PipelineConfigError):
        load_config_data(path)


def test_load_config_data_missing(tmp_path: Path) -> None:
    with pytest.raises(PipelineConfigError):
        load_config_data(tmp_path / "nope.yaml")


def test_load_pipeline_validates(tmp_path: Path) -> None:
    good = tmp_path / "good.yaml"
    good.write_text(YAML_DOC, encoding="utf-8")
    job = load_pipeline(good)
    assert job.name == "daily"

    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\nsteps: []\n", encoding="utf-8")
    with pytest.raises(PipelineConfigError):
        load_pipeline(bad)
