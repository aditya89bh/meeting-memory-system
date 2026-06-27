"""Validate that the bundled example organizations import and yield insights."""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_memory.intelligence import AnalysisFilters
from meeting_memory.services import IntelligenceService, MeetingService

ORG_ROOT = Path(__file__).resolve().parent.parent / "examples" / "organizations"
ORGS = ("startup", "saas", "enterprise", "research-lab", "university")


@pytest.mark.parametrize("org", ORGS)
def test_example_organization_yields_intelligence(org: str, tmp_path: Path) -> None:
    db = tmp_path / f"{org}.db"
    result = MeetingService(db).import_path(ORG_ROOT / org, recursive=True)
    assert result.meetings_imported == 3
    assert result.memories_stored > 0

    report = IntelligenceService(db).report(AnalysisFilters())
    titles = " | ".join(insight.title for insight in report.insights).lower()
    assert "decision revisited" in titles
    assert "risk recurred" in titles
    assert 0.0 <= report.health.overall <= 1.0


def test_all_organizations_present() -> None:
    found = {p.name for p in ORG_ROOT.iterdir() if p.is_dir()}
    assert set(ORGS) <= found
