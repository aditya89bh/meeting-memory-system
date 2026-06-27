"""The deterministic memory extraction pipeline.

The pipeline ties the extraction layer together:

```
Meeting
  -> scan each utterance
  -> run the active extractor registry
  -> collect memory candidates
  -> deduplicate (optional)
  -> validate (drop invalid, surface warnings)
  -> filter by minimum confidence (optional)
  -> ExtractionResult
```

It is configurable (which extractor types are active, a minimum-confidence
floor, whether to deduplicate) and fully deterministic: given the same meeting,
configuration, and clock it always returns the same result.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..models import Meeting
from .dedup import deduplicate
from .extractors import default_extractors
from .extractors.base import ExtractionContext, Extractor
from .models import MEMORY_TYPE_ORDER, ExtractedMemory, ExtractionResult, MemoryType
from .validation import partition_valid

_TYPE_INDEX: dict[MemoryType, int] = {
    memory_type: index for index, memory_type in enumerate(MEMORY_TYPE_ORDER)
}
_SLUG_RE = re.compile(r"[^\w]+")


def derive_meeting_id(meeting: Meeting) -> str:
    """Derive a stable meeting id from a meeting's metadata.

    Prefers the source file stem, then a slug of the title, falling back to the
    literal ``"meeting"`` so a result always has a non-empty id.
    """
    metadata = meeting.metadata
    if metadata.source_path:
        stem = Path(metadata.source_path).stem
        if stem:
            return stem
    if metadata.title:
        slug = _SLUG_RE.sub("-", metadata.title.strip().lower()).strip("-")
        if slug:
            return slug
    return "meeting"


@dataclass(frozen=True)
class ExtractionConfig:
    """Tunable options for an extraction run.

    Attributes:
        enabled_types: The memory types to extract. ``None`` means "all types".
        min_confidence: Drop memories scoring below this threshold (``0`` keeps all).
        deduplicate: Whether to collapse duplicate memories within the meeting.
    """

    enabled_types: frozenset[MemoryType] | None = None
    min_confidence: float = 0.0
    deduplicate: bool = True


def _sort_key(memory: ExtractedMemory) -> tuple[int, int]:
    """Order memories by utterance, then by canonical memory-type order."""
    return (memory.utterance_index, _TYPE_INDEX[memory.memory_type])


class ExtractionPipeline:
    """Runs a registry of extractors over a meeting to produce memories."""

    def __init__(self, extractors: Sequence[Extractor] | None = None) -> None:
        """Build a pipeline from ``extractors`` (defaults to every built-in one)."""
        self._extractors: tuple[Extractor, ...] = (
            tuple(extractors) if extractors is not None else tuple(default_extractors())
        )

    @property
    def extractors(self) -> tuple[Extractor, ...]:
        """The extractors registered on this pipeline, in their run order."""
        return self._extractors

    def extract(
        self,
        meeting: Meeting,
        *,
        meeting_id: str | None = None,
        config: ExtractionConfig | None = None,
        now: datetime | None = None,
    ) -> ExtractionResult:
        """Extract memories from ``meeting`` and return an :class:`ExtractionResult`.

        Args:
            meeting: The parsed meeting to analyse.
            meeting_id: Explicit id; derived from metadata when omitted.
            config: Extraction options; defaults to all types, no floor, dedup on.
            now: Timestamp stamped on every memory; defaults to the current UTC
                time. Pass an explicit value for reproducible output.
        """
        config = config or ExtractionConfig()
        resolved_id = meeting_id or derive_meeting_id(meeting)
        moment = now if now is not None else datetime.now(timezone.utc)
        context = ExtractionContext(meeting_id=resolved_id, extracted_at=moment)

        active = self._active_extractors(config.enabled_types)
        candidates: list[ExtractedMemory] = []
        for utterance in meeting:
            for extractor in active:
                candidates.extend(extractor.extract(utterance, context))

        if config.deduplicate:
            candidates = deduplicate(candidates)

        valid, warnings = partition_valid(candidates, utterance_count=len(meeting))

        if config.min_confidence > 0.0:
            valid = [m for m in valid if m.confidence >= config.min_confidence]

        valid.sort(key=_sort_key)

        return ExtractionResult(
            meeting_id=resolved_id,
            memories=tuple(valid),
            meeting_metadata=meeting.metadata.to_dict(),
            warnings=tuple(warnings),
        )

    def _active_extractors(
        self, enabled_types: Iterable[MemoryType] | None
    ) -> tuple[Extractor, ...]:
        """Filter the registry down to the enabled memory types."""
        if enabled_types is None:
            return self._extractors
        allowed = frozenset(enabled_types)
        return tuple(e for e in self._extractors if e.memory_type in allowed)


_DEFAULT_PIPELINE = ExtractionPipeline()


def extract_memories(
    meeting: Meeting,
    *,
    meeting_id: str | None = None,
    config: ExtractionConfig | None = None,
    now: datetime | None = None,
) -> ExtractionResult:
    """Extract memories from ``meeting`` using the shared default pipeline."""
    return _DEFAULT_PIPELINE.extract(meeting, meeting_id=meeting_id, config=config, now=now)
