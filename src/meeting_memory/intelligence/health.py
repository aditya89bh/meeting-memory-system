"""Meeting-level metrics feeding the organizational-health snapshot.

The engine composes :class:`OrganizationalHealth` from the discovered metric
providers plus context-level signals (knowledge reuse, collaboration, resolution
time). This module contributes the meeting block — volume, productivity, and
repeated-discussion rate — and registers it for discovery.
"""

from __future__ import annotations

from .analysis import content_groups
from .context import AnalysisContext
from .models import InsightCategory, MeetingMetrics
from .providers import MetricProvider, ProviderMetadata
from .registry import register_metric


def meeting_metrics(context: AnalysisContext) -> MeetingMetrics:
    """Compute aggregate meeting statistics for ``context``."""
    total_meetings = len(context.meetings)
    total_memories = len(context.memories)
    if total_meetings == 0:
        return MeetingMetrics(total_memories=total_memories)

    decisions = len(context.by_type("decision"))
    commitments = len(context.by_type("commitment"))
    productivity = round((decisions + commitments) / total_meetings, 4)
    avg_memories = round(total_memories / total_meetings, 4)

    groups = content_groups(list(context.memories))
    repeated_groups = sum(1 for items in groups.values() if len({m.meeting_id for m in items}) > 1)
    repeated_rate = round(repeated_groups / len(groups), 4) if groups else 0.0

    return MeetingMetrics(
        total_meetings=total_meetings,
        total_memories=total_memories,
        avg_memories_per_meeting=avg_memories,
        productivity=productivity,
        repeated_discussion_rate=repeated_rate,
        span_days=context.span_days,
    )


class MeetingMetricProvider(MetricProvider):
    """Provider exposing :func:`meeting_metrics`."""

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="meeting-metrics",
            version="1.0",
            category=InsightCategory.MEETING,
            description="Meeting volume, productivity, and repeated-discussion rate.",
        )

    def analyze(self, context: AnalysisContext) -> MeetingMetrics:
        return meeting_metrics(context)


register_metric(MeetingMetricProvider())

__all__ = ["MeetingMetricProvider", "meeting_metrics"]
