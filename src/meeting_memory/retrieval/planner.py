"""Deterministic query planner.

The planner turns a free-text query plus structured fields into an executable
:class:`RetrievalFilter`. It recognises memory-type words, lifecycle statuses,
month names, and (given a vocabulary) known speakers/participants; anything left
over becomes keyword search terms. The mapping is a fixed lexicon — there is no
learning, randomness, or network access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..storage import MemoryStatus
from .models import RetrievalFilter, RetrievalQuery

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_TYPE_LEXICON: dict[str, str] = {
    "decision": "decision",
    "decisions": "decision",
    "commitment": "commitment",
    "commitments": "commitment",
    "risk": "risk",
    "risks": "risk",
    "assumption": "assumption",
    "assumptions": "assumption",
    "question": "question",
    "questions": "question",
    "fact": "fact",
    "facts": "fact",
}

_STATUS_LEXICON: dict[str, MemoryStatus] = {member.value: member for member in MemoryStatus}

_MONTH_LEXICON: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# Common words that carry no retrieval signal; dropped before keyword matching.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "all",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "been",
        "by",
        "did",
        "do",
        "does",
        "during",
        "every",
        "for",
        "from",
        "had",
        "has",
        "have",
        "in",
        "involved",
        "is",
        "it",
        "later",
        "me",
        "of",
        "on",
        "or",
        "related",
        "show",
        "since",
        "so",
        "still",
        "that",
        "the",
        "their",
        "them",
        "there",
        "these",
        "this",
        "those",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "which",
        "who",
        "why",
        "with",
        "you",
    }
)


@dataclass(frozen=True)
class PlannerVocabulary:
    """Known speakers and participants used to resolve names in free text."""

    speakers: frozenset[str] = frozenset()
    participants: frozenset[str] = frozenset()

    def speaker_lookup(self) -> dict[str, str]:
        """Lowercase token -> canonical speaker name."""
        return {name.lower(): name for name in self.speakers}

    def participant_lookup(self) -> dict[str, str]:
        """Lowercase token -> canonical participant name."""
        return {name.lower(): name for name in self.participants}


class QueryPlanner:
    """Convert a :class:`RetrievalQuery` into a :class:`RetrievalFilter`."""

    def plan(
        self, query: RetrievalQuery, vocabulary: PlannerVocabulary | None = None
    ) -> RetrievalFilter:
        """Plan ``query`` against an optional ``vocabulary`` of known names."""
        vocab = vocabulary or PlannerVocabulary()
        speaker_lookup = vocab.speaker_lookup()
        participant_lookup = vocab.participant_lookup()

        memory_types = set(query.memory_types)
        statuses = set(query.statuses)
        speakers = set(query.speakers)
        participants = set(query.participants)
        months = set(query.months)
        terms: list[str] = []

        tokens = _TOKEN_RE.findall(query.text.lower()) if query.text else []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if token == "open" and following in {"loop", "loops"}:
                memory_types.add("open_loop")
                index += 2
                continue
            if token in _TYPE_LEXICON:
                memory_types.add(_TYPE_LEXICON[token])
            elif token in _STATUS_LEXICON:
                statuses.add(_STATUS_LEXICON[token])
            elif token in _MONTH_LEXICON:
                months.add(_MONTH_LEXICON[token])
            elif token in speaker_lookup:
                speakers.add(speaker_lookup[token])
            elif token in participant_lookup:
                participants.add(participant_lookup[token])
            elif token not in _STOPWORDS:
                terms.append(token)
            index += 1

        return RetrievalFilter(
            terms=tuple(terms),
            phrase=query.text.strip() if query.text else None,
            memory_types=frozenset(memory_types),
            statuses=frozenset(statuses),
            speakers=frozenset(speakers),
            meeting_ids=frozenset(query.meeting_ids),
            participants=frozenset(participants),
            months=frozenset(months),
            min_confidence=query.min_confidence,
            max_confidence=query.max_confidence,
            date_from=query.date_from,
            date_to=query.date_to,
            limit=query.limit,
            offset=query.offset,
        )
