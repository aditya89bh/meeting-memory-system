"""Declarative pipeline configuration (Phase 7).

Pipelines can be described in YAML or JSON and turned into an
:class:`~meeting_memory.connectors.models.AutomationJob`. To stay dependency-free
(no PyYAML), this module ships a small, deterministic parser for the YAML subset
the configs actually use: block mappings, block sequences, nested indentation,
scalars (str/int/float/bool/null), quoted strings, and ``#`` comments.

Configurations are validated before execution so a bad pipeline fails fast with a
clear message rather than midway through a run.

Example::

    name: daily
    schedule:
      frequency: daily
    steps:
      - type: import
        source: examples/history
        recursive: true
      - type: graph
      - type: intelligence
      - type: export
        format: markdown
        output: report.md
"""

from __future__ import annotations

import json
from pathlib import Path

from ..exceptions import PipelineConfigError, ScheduleError
from .models import AutomationJob, Schedule, ScheduleFrequency, StepConfig
from .scheduler import parse_cron

VALID_STEP_TYPES: frozenset[str] = frozenset({"import", "graph", "intelligence", "export"})


def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment that is not inside a quoted string."""
    in_single = in_double = False
    out: list[str] = []
    for char in line:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            break
        out.append(char)
    return "".join(out)


def _tokenize(text: str) -> list[tuple[int, str]]:
    """Split text into ``(indent, content)`` pairs, dropping blanks and comments."""
    tokens: list[tuple[int, str]] = []
    for raw in text.splitlines():
        without_comment = _strip_comment(raw)
        content = without_comment.strip()
        if not content:
            continue
        leading = without_comment[: len(without_comment) - len(without_comment.lstrip())]
        if "\t" in leading:
            raise PipelineConfigError("tabs are not allowed in YAML indentation")
        tokens.append((len(leading), content))
    return tokens


def _parse_scalar(token: str) -> object:
    """Coerce a scalar token into a Python value."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
        return token[1:-1]
    lowered = token.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if lowered in {"null", "~", ""}:
        return None
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _looks_like_mapping(content: str) -> bool:
    key, sep, _ = content.partition(":")
    return bool(sep) and bool(key.strip())


def _parse_block(tokens: list[tuple[int, str]], index: int) -> tuple[object, int]:
    indent, content = tokens[index]
    if content == "-" or content.startswith("- "):
        return _parse_sequence(tokens, index, indent)
    return _parse_mapping(tokens, index, indent)


def _parse_sequence(
    tokens: list[tuple[int, str]], index: int, indent: int
) -> tuple[list[object], int]:
    items: list[object] = []
    i = index
    while i < len(tokens):
        cur_indent, content = tokens[i]
        if cur_indent != indent or not (content == "-" or content.startswith("- ")):
            break
        rest = content[1:].strip()
        if rest == "":
            if i + 1 < len(tokens) and tokens[i + 1][0] > indent:
                value, i = _parse_block(tokens, i + 1)
            else:
                value, i = None, i + 1
        elif _looks_like_mapping(rest):
            key_indent = indent + 2
            sub: list[tuple[int, str]] = [(key_indent, rest)]
            j = i + 1
            while j < len(tokens) and tokens[j][0] >= key_indent:
                sub.append(tokens[j])
                j += 1
            value, _ = _parse_mapping(sub, 0, key_indent)
            i = j
        else:
            value, i = _parse_scalar(rest), i + 1
        items.append(value)
    return items, i


def _parse_mapping(
    tokens: list[tuple[int, str]], index: int, indent: int
) -> tuple[dict[str, object], int]:
    mapping: dict[str, object] = {}
    i = index
    while i < len(tokens):
        cur_indent, content = tokens[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise PipelineConfigError(f"unexpected indentation at: {content!r}")
        key, sep, inline = content.partition(":")
        if not sep:
            raise PipelineConfigError(f"expected 'key: value', got: {content!r}")
        key = key.strip()
        inline = inline.strip()
        if inline == "":
            if i + 1 < len(tokens) and tokens[i + 1][0] > indent:
                value, i = _parse_block(tokens, i + 1)
            elif (
                i + 1 < len(tokens)
                and tokens[i + 1][0] == indent
                and (tokens[i + 1][1] == "-" or tokens[i + 1][1].startswith("- "))
            ):
                value, i = _parse_sequence(tokens, i + 1, indent)
            else:
                value, i = None, i + 1
        else:
            value, i = _parse_scalar(inline), i + 1
        mapping[key] = value
    return mapping, i


def parse_yaml(text: str) -> object:
    """Parse a YAML-subset document into Python primitives."""
    tokens = _tokenize(text)
    if not tokens:
        return None
    value, _ = _parse_block(tokens, 0)
    return value


def load_config_data(path: str | Path) -> dict[str, object]:
    """Load a pipeline configuration file (YAML or JSON) into a mapping."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PipelineConfigError(f"cannot read pipeline config {file_path}: {exc}") from exc

    suffix = file_path.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PipelineConfigError(f"invalid JSON pipeline config: {exc}") from exc
    else:
        data = parse_yaml(text)

    if not isinstance(data, dict):
        raise PipelineConfigError("pipeline config must be a mapping at the top level")
    return data


def _build_schedule(value: object) -> Schedule:
    """Build a :class:`Schedule` from a string or mapping config value."""
    if value is None:
        return Schedule()
    if isinstance(value, str):
        frequency = value
        expression = None
        at = None
    elif isinstance(value, dict):
        frequency = str(value.get("frequency", "manual"))
        raw_expr = value.get("expression", value.get("cron"))
        expression = str(raw_expr) if raw_expr is not None else None
        raw_at = value.get("at")
        at = str(raw_at) if raw_at is not None else None
    else:
        raise PipelineConfigError(f"invalid schedule definition: {value!r}")
    try:
        parsed_frequency = ScheduleFrequency(frequency)
    except ValueError as exc:
        choices = ", ".join(member.value for member in ScheduleFrequency)
        raise PipelineConfigError(
            f"unknown schedule frequency {frequency!r}; choose from: {choices}"
        ) from exc
    return Schedule(frequency=parsed_frequency, expression=expression, at=at)


def _build_step(value: object) -> StepConfig:
    """Build a :class:`StepConfig` from a config mapping."""
    if not isinstance(value, dict):
        raise PipelineConfigError(f"each step must be a mapping, got: {value!r}")
    step_type = value.get("type")
    if not isinstance(step_type, str) or not step_type:
        raise PipelineConfigError(f"each step requires a string 'type': {value!r}")
    params = {key: val for key, val in value.items() if key != "type"}
    return StepConfig(type=step_type, params=params)


def build_job(data: dict[str, object]) -> AutomationJob:
    """Build an :class:`AutomationJob` from parsed configuration data."""
    name = str(data.get("name", "pipeline"))
    enabled = bool(data.get("enabled", True))
    schedule = _build_schedule(data.get("schedule"))
    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list):
        raise PipelineConfigError("'steps' must be a list")
    steps = tuple(_build_step(step) for step in raw_steps)
    return AutomationJob(name=name, steps=steps, schedule=schedule, enabled=enabled)


def validate_job(job: AutomationJob) -> list[str]:
    """Return validation problems for a job (empty when the job is valid)."""
    problems: list[str] = []
    if not job.name:
        problems.append("job name must not be empty")
    if not job.steps:
        problems.append("pipeline must declare at least one step")
    for position, step in enumerate(job.steps):
        if step.type not in VALID_STEP_TYPES:
            choices = ", ".join(sorted(VALID_STEP_TYPES))
            problems.append(f"step {position}: unknown type {step.type!r}; choose from: {choices}")
            continue
        if step.type == "import" and not (step.params.get("source") or step.params.get("sources")):
            problems.append(f"step {position}: import step requires 'source' or 'sources'")
        if step.type == "export" and not step.params.get("format"):
            problems.append(f"step {position}: export step requires 'format'")
    if job.schedule.frequency is ScheduleFrequency.CRON:
        if not job.schedule.expression:
            problems.append("cron schedule requires an 'expression'")
        else:
            try:
                parse_cron(job.schedule.expression)
            except ScheduleError as exc:
                problems.append(f"invalid cron expression: {exc}")
    return problems


def load_pipeline(path: str | Path) -> AutomationJob:
    """Load, build, and validate a pipeline configuration file."""
    job = build_job(load_config_data(path))
    problems = validate_job(job)
    if problems:
        joined = "; ".join(problems)
        raise PipelineConfigError(f"invalid pipeline configuration: {joined}")
    return job
