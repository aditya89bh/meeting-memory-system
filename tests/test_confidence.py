"""Unit tests for deterministic confidence scoring."""

from __future__ import annotations

import pytest

from meeting_memory.extraction.confidence import (
    HEDGE_PENALTY,
    HIGH,
    clamp,
    has_hedge,
    score,
    score_for_text,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-1.0, 0.0), (0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (2.0, 1.0)],
)
def test_clamp(value: float, expected: float) -> None:
    assert clamp(value) == expected


@pytest.mark.parametrize(
    "text",
    ["maybe we ship", "I think so", "this might work", "not sure yet", "could be"],
)
def test_has_hedge_true(text: str) -> None:
    assert has_hedge(text)


@pytest.mark.parametrize("text", ["we decided", "this is approved", "ship it"])
def test_has_hedge_false(text: str) -> None:
    assert not has_hedge(text)


def test_score_combines_and_rounds() -> None:
    assert score(0.6, boost=0.15) == 0.75
    assert score(0.85, boost=0.1) == 0.95
    assert score(0.85, penalty=0.2) == 0.65


def test_score_clamped_to_unit_interval() -> None:
    assert score(0.95, boost=0.5) == 1.0
    assert score(0.1, penalty=0.5) == 0.0


def test_score_for_text_applies_hedge_penalty() -> None:
    assert score_for_text(HIGH, "we will do it") == score(HIGH)
    assert score_for_text(HIGH, "we will maybe do it") == score(HIGH, penalty=HEDGE_PENALTY)
