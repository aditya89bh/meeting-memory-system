"""Deterministic benchmark dataset generators.

Every dataset is fully reproducible: given the same :class:`DatasetSpec` (and its
seed) the generated transcripts are byte-for-byte identical. Datasets contain
multiple projects and people, recurring risks, evolving decisions, long weekly
timelines, and explicit cross-meeting references, so they exercise the parser,
extraction, storage, retrieval, graph, and intelligence layers realistically.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

_PROJECT_POOL: tuple[str, ...] = (
    "Atlas",
    "Borealis",
    "Cobalt",
    "Dynamo",
    "Everest",
    "Falcon",
    "Granite",
    "Helios",
    "Ionic",
    "Juniper",
    "Krypton",
    "Lumen",
)

_PERSON_POOL: tuple[str, ...] = (
    "Priya",
    "Marco",
    "Lena",
    "Devin",
    "Sofia",
    "Owen",
    "Maya",
    "Hassan",
    "Greta",
    "Ravi",
    "Nora",
    "Theo",
    "Iris",
    "Quinn",
    "Pavel",
    "Yara",
)

_CHOICES: tuple[str, ...] = (
    "PostgreSQL",
    "a managed message queue",
    "a monorepo layout",
    "weekly release trains",
    "a feature-flag rollout",
    "an event-sourced core",
)

_RISKS: tuple[str, ...] = (
    "the vendor API rate limits will slow ingestion",
    "the migration could fail under peak load",
    "the staging environment is a bottleneck",
    "an unreviewed dependency may delay the release",
    "the data retention policy is a blocker",
)

_ASSUMPTIONS: tuple[str, ...] = (
    "the budget is approved",
    "the pilot customer represents typical usage",
    "the third-party SLA holds",
    "traffic stays within current projections",
)

_OPEN_ITEMS: tuple[str, ...] = (
    "onboarding documentation",
    "the data retention policy",
    "the incident runbook",
    "the capacity plan",
)

_ARTIFACTS: tuple[str, ...] = (
    "staging environment",
    "ingestion pipeline",
    "dashboard",
    "backup job",
    "load test harness",
)

_QUESTIONS: tuple[str, ...] = (
    "confirm the data retention policy",
    "expand the pilot to a second customer",
    "freeze the schema before launch",
    "add a read replica",
)

_WEEKDAYS: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
)


@dataclass(frozen=True)
class DatasetSpec:
    """A reproducible description of a benchmark dataset."""

    name: str
    projects: int
    people: int
    meetings: int
    utterances_per_meeting: int
    seed: int = 1729
    start_date: str = "2025-01-06"

    def estimated_utterances(self) -> int:
        """Return the total number of generated utterances across all meetings."""
        return self.meetings * self.utterances_per_meeting


@dataclass(frozen=True)
class GeneratedMeeting:
    """A single generated transcript ready to be written or imported."""

    filename: str
    title: str
    date: str
    project: str
    content: str


DATASET_PRESETS: dict[str, DatasetSpec] = {
    "small": DatasetSpec("small", projects=2, people=4, meetings=6, utterances_per_meeting=12),
    "medium": DatasetSpec("medium", projects=4, people=8, meetings=40, utterances_per_meeting=16),
    "large": DatasetSpec("large", projects=8, people=14, meetings=200, utterances_per_meeting=20),
    "enterprise": DatasetSpec(
        "enterprise", projects=12, people=16, meetings=600, utterances_per_meeting=24
    ),
}


def get_preset(name: str) -> DatasetSpec:
    """Return a named dataset preset (small/medium/large/enterprise)."""
    try:
        return DATASET_PRESETS[name]
    except KeyError:
        choices = ", ".join(sorted(DATASET_PRESETS))
        raise KeyError(f"unknown dataset {name!r}; choose from: {choices}") from None


def _pool(values: Sequence[str], count: int) -> tuple[str, ...]:
    """Return the first ``count`` entries of ``values`` (cycling if needed)."""
    if count <= len(values):
        return tuple(values[:count])
    base = list(values)
    repeated = (base * (count // len(base) + 1))[:count]
    return tuple(repeated)


def _timestamp(index: int) -> str:
    """Return a ``[HH:MM:SS]`` timestamp for the ``index``-th utterance."""
    total = index * 20
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"


def _sentences(
    spec: DatasetSpec,
    rng: random.Random,
    *,
    project: str,
    people: Sequence[str],
    risk: str,
    choice: str,
    meeting_index: int,
    prev_title: str | None,
) -> list[tuple[str, str]]:
    """Build a deterministic list of ``(speaker, text)`` utterances for a meeting."""
    lines: list[tuple[str, str]] = []

    def speaker() -> str:
        return str(rng.choice(people))

    lead = people[0]
    lines.append((lead, f"Welcome to the Project {project} sync, let's review progress."))
    if prev_title is not None:
        lines.append(
            (lead, f"As decided in {prev_title}, we continue with {choice} for Project {project}.")
        )
    if meeting_index == 0:
        lines.append((lead, f"We decided to build Project {project} on {choice}."))
    else:
        new_choice = rng.choice(_CHOICES)
        lines.append(
            (lead, f"We agreed to switch to {new_choice} for Project {project} going forward.")
        )

    # Recurring, project-specific risk so risk-recurrence insights fire.
    lines.append((speaker(), f"There is a risk that {risk}."))

    builders: list[Callable[[], tuple[str, str]]] = [
        lambda: (
            speaker(),
            f"I will set up the {rng.choice(_ARTIFACTS)} by {rng.choice(_WEEKDAYS)}.",
        ),
        lambda: (
            speaker(),
            f"The {rng.choice(_ARTIFACTS)} is assigned to {speaker()}, due by "
            f"{rng.choice(_WEEKDAYS)}.",
        ),
        lambda: (speaker(), f"We are assuming {rng.choice(_ASSUMPTIONS)} for this quarter."),
        lambda: (
            speaker(),
            f"The {rng.choice(_OPEN_ITEMS)} is still open and needs to be decided.",
        ),
        lambda: (speaker(), f"Should we {rng.choice(_QUESTIONS)}?"),
        lambda: (
            speaker(),
            f"Project {project} currently serves the {rng.choice(_ARTIFACTS)} workload.",
        ),
    ]
    while len(lines) < spec.utterances_per_meeting:
        builder = builders[len(lines) % len(builders)]
        lines.append(builder())
    return lines[: spec.utterances_per_meeting]


def generate_dataset(spec: DatasetSpec) -> list[GeneratedMeeting]:
    """Generate the full, deterministic list of meetings for ``spec``."""
    rng = random.Random(spec.seed)
    projects = _pool(_PROJECT_POOL, spec.projects)
    people = _pool(_PERSON_POOL, spec.people)
    base = date.fromisoformat(spec.start_date)

    # Assign each project a stable recurring risk and an initial decision choice.
    project_risk = {name: _RISKS[index % len(_RISKS)] for index, name in enumerate(projects)}
    project_choice = {name: _CHOICES[index % len(_CHOICES)] for index, name in enumerate(projects)}
    project_meeting_count: dict[str, int] = dict.fromkeys(projects, 0)
    project_last_title: dict[str, str | None] = dict.fromkeys(projects, None)

    meetings: list[GeneratedMeeting] = []
    width = len(str(spec.meetings))
    for index in range(spec.meetings):
        project = projects[index % len(projects)]
        local_index = project_meeting_count[project]
        project_meeting_count[project] = local_index + 1
        meeting_date = base + timedelta(days=7 * (index // len(projects)) + index % len(projects))
        title = f"Project {project} Sync {local_index + 1}"

        # Rotate the active people for this meeting so ownership varies deterministically.
        offset = index % len(people)
        rotated = tuple(people[offset:] + people[:offset])
        utterances = _sentences(
            spec,
            rng,
            project=project,
            people=rotated,
            risk=project_risk[project],
            choice=project_choice[project],
            meeting_index=local_index,
            prev_title=project_last_title[project],
        )
        project_last_title[project] = title

        header = [
            "---",
            f"title: {title}",
            f"date: {meeting_date.isoformat()}",
            f"project: {project}",
            "---",
        ]
        body = [
            f"{_timestamp(position)} {speaker}: {text}"
            for position, (speaker, text) in enumerate(utterances)
        ]
        content = "\n".join(header + body) + "\n"
        filename = f"meeting-{index + 1:0{width}d}.txt"
        meetings.append(
            GeneratedMeeting(
                filename=filename,
                title=title,
                date=meeting_date.isoformat(),
                project=project,
                content=content,
            )
        )
    return meetings


def write_dataset(spec: DatasetSpec, directory: str | Path) -> list[Path]:
    """Generate ``spec`` and write each transcript into ``directory``."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for meeting in generate_dataset(spec):
        path = target / meeting.filename
        path.write_text(meeting.content, encoding="utf-8")
        written.append(path)
    return written
