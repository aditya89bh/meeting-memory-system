"""Unit tests for each rule-based extractor."""

from __future__ import annotations

from datetime import datetime, timezone

from meeting_memory.extraction.confidence import HIGH, MEDIUM, MEDIUM_HIGH, VERY_HIGH, score
from meeting_memory.extraction.extractors import (
    AssumptionExtractor,
    CommitmentExtractor,
    DecisionExtractor,
    FactExtractor,
    OpenLoopExtractor,
    QuestionExtractor,
    RiskExtractor,
    default_extractors,
)
from meeting_memory.extraction.extractors.base import ExtractionContext, Extractor
from meeting_memory.extraction.models import (
    CommitmentMemory,
    ExtractedMemory,
    MemoryType,
)
from meeting_memory.models import Speaker, Utterance

_CTX = ExtractionContext(meeting_id="m", extracted_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def _utt(text: str, index: int = 0, speaker: str = "Alice") -> Utterance:
    return Utterance(index=index, speaker=Speaker(speaker), text=text)


def _run(
    extractor: Extractor, text: str, index: int = 0, speaker: str = "Alice"
) -> list[ExtractedMemory]:
    return extractor.extract(_utt(text, index, speaker), _CTX)


class TestDecisionExtractor:
    def test_we_decided_is_very_high(self) -> None:
        memories = _run(DecisionExtractor(), "We decided to use Postgres.")
        assert len(memories) == 1
        memory = memories[0]
        assert memory.memory_type is MemoryType.DECISION
        assert memory.confidence == score(VERY_HIGH)
        assert memory.memory_id == "m:decision:0"
        assert memory.evidence.text.lower() == "we decided"

    def test_approved(self) -> None:
        assert _run(DecisionExtractor(), "The plan was approved.")[0].confidence == score(HIGH)

    def test_lets_go_with(self) -> None:
        assert _run(DecisionExtractor(), "Let's go with option B.")

    def test_we_will_use_is_medium_high(self) -> None:
        memory = _run(DecisionExtractor(), "We will use Redis for the cache.")[0]
        assert memory.confidence == score(MEDIUM_HIGH)

    def test_strongest_rule_wins(self) -> None:
        memory = _run(DecisionExtractor(), "We decided this is approved.")[0]
        assert memory.confidence == score(VERY_HIGH)
        assert memory.evidence.text.lower() == "we decided"

    def test_no_match(self) -> None:
        assert _run(DecisionExtractor(), "Let's review the metrics.") == []

    def test_tie_break_prefers_earlier_match(self) -> None:
        # Two equal-confidence rules match ("decision is" and "approved");
        # the one starting earlier in the text wins.
        memory = _run(DecisionExtractor(), "Approved, the decision is final.")[0]
        assert memory.evidence.text.lower() == "approved"
        assert memory.confidence == score(HIGH)

    def test_hedging_lowers_confidence(self) -> None:
        memory = _run(DecisionExtractor(), "We decided, but maybe we revisit later.")[0]
        assert memory.confidence == score(VERY_HIGH, penalty=0.2)


class TestCommitmentExtractor:
    def test_first_person_owner_is_speaker(self) -> None:
        memory = _run(CommitmentExtractor(), "I will send the notes.", speaker="Bob")[0]
        assert isinstance(memory, CommitmentMemory)
        assert memory.owner == "Bob"
        assert memory.due is None

    def test_owner_and_deadline_boost(self) -> None:
        memory = _run(CommitmentExtractor(), "I will finish the deck by Friday.", speaker="Bob")
        commitment = memory[0]
        assert isinstance(commitment, CommitmentMemory)
        assert commitment.owner == "Bob"
        assert commitment.due == "by Friday"
        assert commitment.confidence == score(HIGH, boost=0.1)

    def test_assigned_to_names_owner(self) -> None:
        memory = _run(CommitmentExtractor(), "The rollout is assigned to Dana for this sprint.")[0]
        assert isinstance(memory, CommitmentMemory)
        assert memory.owner == "Dana"

    def test_can_you(self) -> None:
        assert _run(CommitmentExtractor(), "Can you prepare the report.")

    def test_no_match(self) -> None:
        assert _run(CommitmentExtractor(), "The weather is nice.") == []


class TestOpenLoopExtractor:
    def test_pending(self) -> None:
        assert _run(OpenLoopExtractor(), "The contract is pending.")[0].memory_type is (
            MemoryType.OPEN_LOOP
        )

    def test_tbd_high(self) -> None:
        assert _run(OpenLoopExtractor(), "Pricing is TBD.")[0].confidence == score(HIGH)

    def test_follow_up(self) -> None:
        assert _run(OpenLoopExtractor(), "Let's follow up next week.")

    def test_needs_to_be_decided(self) -> None:
        assert _run(OpenLoopExtractor(), "This needs to be decided soon.")[0].confidence == (
            score(HIGH)
        )

    def test_no_match(self) -> None:
        assert _run(OpenLoopExtractor(), "Everything is on track.") == []


class TestRiskExtractor:
    def test_risk(self) -> None:
        assert _run(RiskExtractor(), "There is a risk of data loss.")[0].memory_type is (
            MemoryType.RISK
        )

    def test_blocker_high(self) -> None:
        assert _run(RiskExtractor(), "SSO is a blocker.")[0].confidence == score(HIGH)

    def test_might_fail_is_hedge_penalised(self) -> None:
        # "might fail" is a strong risk trigger, but "might" is also a hedge word,
        # so the deterministic score applies the hedging penalty.
        memory = _run(RiskExtractor(), "The job might fail under load.")[0]
        assert memory.confidence == score(HIGH, penalty=0.2)

    def test_dependency(self) -> None:
        assert _run(RiskExtractor(), "We have a dependency on the vendor.")

    def test_no_match(self) -> None:
        assert _run(RiskExtractor(), "The demo went smoothly.") == []


class TestAssumptionExtractor:
    def test_assuming(self) -> None:
        assert _run(AssumptionExtractor(), "Assuming traffic stays flat.")[0].memory_type is (
            MemoryType.ASSUMPTION
        )

    def test_based_on_assumption_very_high(self) -> None:
        memory = _run(AssumptionExtractor(), "Based on the assumption that demand holds.")[0]
        assert memory.confidence == score(VERY_HIGH)

    def test_if_this_holds(self) -> None:
        assert _run(AssumptionExtractor(), "If this holds, we are fine.")

    def test_no_match(self) -> None:
        assert _run(AssumptionExtractor(), "The results are in.") == []


class TestQuestionExtractor:
    def test_question_mark_is_very_high(self) -> None:
        memory = _run(QuestionExtractor(), "Should we ship this?")[0]
        assert memory.memory_type is MemoryType.QUESTION
        assert memory.confidence == score(VERY_HIGH)
        assert memory.metadata["trigger"] == "?"
        assert memory.evidence.text == "Should we ship this?"

    def test_question_is_phrase(self) -> None:
        memory = _run(QuestionExtractor(), "The question is whether to ship.")[0]
        assert memory.confidence == score(HIGH)

    def test_can_we_without_mark(self) -> None:
        memory = _run(QuestionExtractor(), "Can we revisit the budget")[0]
        assert memory.confidence == score(MEDIUM_HIGH)

    def test_no_match(self) -> None:
        assert _run(QuestionExtractor(), "We are on schedule.") == []


class TestFactExtractor:
    def test_customer_metric_boosted(self) -> None:
        memory = _run(FactExtractor(), "Our top customer needs 99.9% uptime.")[0]
        assert memory.memory_type is MemoryType.FACT
        assert memory.confidence == score(MEDIUM, boost=0.15)

    def test_requirement_without_metric(self) -> None:
        memory = _run(FactExtractor(), "SSO is a hard requirement.")[0]
        assert memory.confidence == score(MEDIUM)

    def test_questions_are_not_facts(self) -> None:
        assert _run(FactExtractor(), "How many customers do we have?") == []

    def test_no_match(self) -> None:
        assert _run(FactExtractor(), "Hello everyone, good morning.") == []


def test_default_extractors_cover_every_type() -> None:
    types = {extractor.memory_type for extractor in default_extractors()}
    assert types == set(MemoryType)
