"""Deterministic confidence scoring for extracted memories.

Confidence is a bounded score in ``[0.0, 1.0]`` derived purely from the matched
phrase strength and a few textual signals. There is no learning or randomness:
the same input always yields the same score, which keeps extraction testable.

Scoring model:

* Each extractor picks a **base** score reflecting how unambiguous its trigger
  phrase is (e.g. "we decided" is stronger than "let's go with").
* **Hedging** language ("maybe", "might", "I think", ...) applies a penalty.
* Extractors may pass a **boost** for corroborating signals (e.g. a commitment
  that names both an owner and a deadline).
"""

from __future__ import annotations

import re

# Canonical base scores, ordered from strongest to weakest signal.
VERY_HIGH = 0.95
HIGH = 0.85
MEDIUM_HIGH = 0.75
MEDIUM = 0.6
LOW = 0.45
VERY_LOW = 0.3

# Adjustments.
HEDGE_PENALTY = 0.2
OWNER_DEADLINE_BOOST = 0.1

_HEDGE_TERMS = (
    "maybe",
    "might",
    "perhaps",
    "possibly",
    "potentially",
    "probably",
    "i think",
    "i guess",
    "i suppose",
    "not sure",
    "kind of",
    "sort of",
    "could be",
    "tentatively",
)
_HEDGE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _HEDGE_TERMS) + r")\b",
    re.IGNORECASE,
)


def clamp(value: float) -> float:
    """Clamp ``value`` into the inclusive range ``[0.0, 1.0]``."""
    return max(0.0, min(1.0, value))


def has_hedge(text: str) -> bool:
    """Return whether ``text`` contains hedging / uncertainty language."""
    return _HEDGE_RE.search(text) is not None


def score(base: float, *, boost: float = 0.0, penalty: float = 0.0) -> float:
    """Combine a base score with boosts and penalties, clamped to ``[0, 1]``.

    The result is rounded to three decimal places for stable serialisation.
    """
    return round(clamp(base + boost - penalty), 3)


def score_for_text(base: float, text: str, *, boost: float = 0.0) -> float:
    """Score ``base`` for ``text``, applying a hedging penalty when present."""
    penalty = HEDGE_PENALTY if has_hedge(text) else 0.0
    return score(base, boost=boost, penalty=penalty)
