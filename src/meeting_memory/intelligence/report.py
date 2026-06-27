"""Deterministic report rendering for the intelligence engine.

Renders an :class:`InsightReport` into JSON, Markdown, or plain text. All three
share the same section layout — executive summary, organizational health,
decision/commitment/risk insights, recommendations, and an appendix of
per-project and per-person metrics — and are byte-for-byte reproducible.
"""

from __future__ import annotations

import json

from .models import (
    Insight,
    InsightCategory,
    InsightReport,
)
from .providers import ProviderMetadata, ReportProvider
from .registry import register_report

REPORT_FORMATS: tuple[str, ...] = ("json", "markdown", "text")


def _decision(report: InsightReport) -> list[Insight]:
    return report.insights_by_category(InsightCategory.DECISION)


def _commitment(report: InsightReport) -> list[Insight]:
    return report.insights_by_category(InsightCategory.COMMITMENT) + report.insights_by_category(
        InsightCategory.PERSON
    )


def _risk(report: InsightReport) -> list[Insight]:
    return report.insights_by_category(InsightCategory.RISK) + report.insights_by_category(
        InsightCategory.PROJECT
    )


def to_json(report: InsightReport) -> str:
    """Render the report as pretty-printed JSON."""
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def to_markdown(report: InsightReport) -> str:
    """Render the report as Markdown."""
    health = report.health
    lines: list[str] = []
    lines.append("# Organizational Intelligence Report")
    lines.append("")
    lines.append(f"Reference date: {report.reference_date or 'n/a'}")
    lines.append("")

    lines.append("## Executive summary")
    lines.append("")
    lines.append(f"- Overall health: **{health.overall:.2f}**")
    lines.append(f"- Insights: {len(report.insights)}")
    lines.append(f"- Recommendations: {len(report.recommendations)}")
    lines.append(
        f"- Decisions: {health.decision.total} (stability {health.decision.stability:.0%})"
    )
    lines.append(
        f"- Commitments: {health.commitment.total} "
        f"(resolved {health.commitment.resolution_rate:.0%})"
    )
    lines.append(f"- Risks: {health.risk.total} (resolved {health.risk.resolution_rate:.0%})")
    lines.append("")

    lines.append("## Organizational health")
    lines.append("")
    lines.append("| Score | Value |")
    lines.append("| --- | --- |")
    for key in sorted(health.scores):
        lines.append(f"| {key} | {health.scores[key]:.4g} |")
    lines.append("")

    _markdown_insight_section(lines, "Decision insights", _decision(report))
    _markdown_insight_section(lines, "Commitment insights", _commitment(report))
    _markdown_insight_section(lines, "Risk insights", _risk(report))

    lines.append("## Recommendations")
    lines.append("")
    if report.recommendations:
        for rec in report.recommendations:
            lines.append(f"- **[{rec.priority}] {rec.title}** — {rec.detail}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append("## Appendix")
    lines.append("")
    lines.append("### Projects")
    lines.append("")
    if report.projects:
        lines.append("| Project | Risks | Decisions | Meetings | Blockers |")
        lines.append("| --- | --- | --- | --- | --- |")
        for project in report.projects:
            lines.append(
                f"| {project.name} | {project.risk_count} | {project.decision_count} "
                f"| {project.meeting_count} | {project.blocker_count} |"
            )
    else:
        lines.append("None")
    lines.append("")
    lines.append("### People")
    lines.append("")
    if report.people:
        lines.append("| Person | Open commitments | Total commitments | Decisions | Meetings |")
        lines.append("| --- | --- | --- | --- | --- |")
        for person in report.people:
            lines.append(
                f"| {person.name} | {person.open_commitments} | "
                f"{person.total_commitments} | {person.decisions_owned} "
                f"| {person.meetings_attended} |"
            )
    else:
        lines.append("None")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _markdown_insight_section(lines: list[str], title: str, insights: list[Insight]) -> None:
    lines.append(f"## {title}")
    lines.append("")
    if insights:
        for insight in insights:
            lines.append(f"- **[{insight.severity}] {insight.title}** — {insight.detail}")
    else:
        lines.append("- None")
    lines.append("")


def to_text(report: InsightReport) -> str:
    """Render the report as plain text."""
    health = report.health
    lines: list[str] = []
    lines.append("ORGANIZATIONAL INTELLIGENCE REPORT")
    lines.append(f"Reference date: {report.reference_date or 'n/a'}")
    lines.append("")
    lines.append("EXECUTIVE SUMMARY")
    lines.append(f"  Overall health: {health.overall:.2f}")
    lines.append(f"  Insights: {len(report.insights)}")
    lines.append(f"  Recommendations: {len(report.recommendations)}")
    lines.append("")
    lines.append("ORGANIZATIONAL HEALTH")
    for key in sorted(health.scores):
        lines.append(f"  {key}: {health.scores[key]:.4g}")
    lines.append("")
    _text_insight_section(lines, "DECISION INSIGHTS", _decision(report))
    _text_insight_section(lines, "COMMITMENT INSIGHTS", _commitment(report))
    _text_insight_section(lines, "RISK INSIGHTS", _risk(report))
    lines.append("RECOMMENDATIONS")
    if report.recommendations:
        for rec in report.recommendations:
            lines.append(f"  [{rec.priority}] {rec.title}: {rec.detail}")
    else:
        lines.append("  None")
    lines.append("")
    lines.append("APPENDIX")
    lines.append("  Projects:")
    for project in report.projects:
        lines.append(
            f"    {project.name}: {project.risk_count} risks, {project.blocker_count} blockers"
        )
    if not report.projects:
        lines.append("    None")
    lines.append("  People:")
    for person in report.people:
        lines.append(
            f"    {person.name}: {person.open_commitments} open commitments, "
            f"{person.decisions_owned} decisions"
        )
    if not report.people:
        lines.append("    None")
    return "\n".join(lines).rstrip() + "\n"


def _text_insight_section(lines: list[str], title: str, insights: list[Insight]) -> None:
    lines.append(title)
    if insights:
        for insight in insights:
            lines.append(f"  [{insight.severity}] {insight.title}: {insight.detail}")
    else:
        lines.append("  None")
    lines.append("")


def render_report(report: InsightReport, fmt: str) -> str:
    """Render ``report`` into ``fmt`` (one of :data:`REPORT_FORMATS`)."""
    if fmt == "json":
        return to_json(report)
    if fmt == "markdown":
        return to_markdown(report)
    if fmt == "text":
        return to_text(report)
    raise ValueError(f"Unknown report format {fmt!r}. Available: {', '.join(REPORT_FORMATS)}")


class JsonReportProvider(ReportProvider):
    """Renders the report as JSON."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="report-json",
            version="1.0",
            category=InsightCategory.ORGANIZATION,
            description="JSON rendering of the intelligence report.",
        )

    def fmt(self) -> str:
        return "json"

    def analyze(self, report: InsightReport) -> str:
        return to_json(report)


class MarkdownReportProvider(ReportProvider):
    """Renders the report as Markdown."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="report-markdown",
            version="1.0",
            category=InsightCategory.ORGANIZATION,
            description="Markdown rendering of the intelligence report.",
        )

    def fmt(self) -> str:
        return "markdown"

    def analyze(self, report: InsightReport) -> str:
        return to_markdown(report)


class TextReportProvider(ReportProvider):
    """Renders the report as plain text."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="report-text",
            version="1.0",
            category=InsightCategory.ORGANIZATION,
            description="Plain-text rendering of the intelligence report.",
        )

    def fmt(self) -> str:
        return "text"

    def analyze(self, report: InsightReport) -> str:
        return to_text(report)


register_report(JsonReportProvider())
register_report(MarkdownReportProvider())
register_report(TextReportProvider())

__all__ = [
    "REPORT_FORMATS",
    "JsonReportProvider",
    "MarkdownReportProvider",
    "TextReportProvider",
    "render_report",
    "to_json",
    "to_markdown",
    "to_text",
]
