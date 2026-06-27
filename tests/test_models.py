"""Unit tests for the typed domain models."""

from __future__ import annotations

from datetime import date

import pytest

from meeting_memory.exceptions import MalformedTranscriptError
from meeting_memory.models import Meeting, Metadata, Speaker, Timestamp, Utterance


class TestTimestamp:
    @pytest.mark.parametrize(
        ("raw", "expected_seconds", "expected_label"),
        [
            ("00:00:05", 5.0, "00:00:05"),
            ("01:02:03", 3723.0, "01:02:03"),
            ("02:30", 150.0, "00:02:30"),
            ("[00:01:00]", 60.0, "00:01:00"),
            ("(00:01:00)", 60.0, "00:01:00"),
            ("90", 90.0, "00:01:30"),
            ("00:00:01.500", 1.5, "00:00:01.500"),
            ("00:00:01,250", 1.25, "00:00:01.250"),
        ],
    )
    def test_parse_supported_formats(
        self, raw: str, expected_seconds: float, expected_label: str
    ) -> None:
        timestamp = Timestamp.parse(raw)
        assert timestamp.total_seconds == expected_seconds
        assert timestamp.label == expected_label

    def test_parse_preserves_raw(self) -> None:
        assert Timestamp.parse(" [00:01:00] ").raw == "[00:01:00]"

    @pytest.mark.parametrize("bad", ["", "abc", "12:60", "::", "1:2:3:4"])
    def test_parse_rejects_invalid(self, bad: str) -> None:
        with pytest.raises(MalformedTranscriptError):
            Timestamp.parse(bad)

    def test_negative_seconds_rejected(self) -> None:
        with pytest.raises(MalformedTranscriptError):
            Timestamp(total_seconds=-1.0)

    def test_ordering_ignores_raw(self) -> None:
        early = Timestamp.from_seconds(10, raw="ten")
        late = Timestamp.from_seconds(20, raw="twenty")
        assert early < late
        assert early == Timestamp.from_seconds(10, raw="different")

    def test_str_and_to_dict(self) -> None:
        timestamp = Timestamp.from_seconds(5)
        assert str(timestamp) == "00:00:05"
        assert timestamp.to_dict() == {"total_seconds": 5.0, "label": "00:00:05"}


class TestSpeaker:
    def test_is_named(self) -> None:
        assert Speaker("Alice").is_named
        assert not Speaker("   ").is_named

    def test_identity_ignores_aliases(self) -> None:
        assert Speaker("Alice", frozenset({"A"})) == Speaker("Alice", frozenset({"B"}))

    def test_to_dict_sorts_aliases(self) -> None:
        speaker = Speaker("Alice", frozenset({"**Alice**", "A."}))
        assert speaker.to_dict() == {"name": "Alice", "aliases": ["**Alice**", "A."]}

    def test_str(self) -> None:
        assert str(Speaker("Bob")) == "Bob"


class TestUtterance:
    def test_word_count(self) -> None:
        utterance = Utterance(0, Speaker("Alice"), "one two three")
        assert utterance.word_count == 3

    def test_to_dict_with_and_without_timestamp(self) -> None:
        with_ts = Utterance(1, Speaker("Bob"), "hi", Timestamp.from_seconds(5))
        assert with_ts.to_dict()["timestamp"] == {"total_seconds": 5.0, "label": "00:00:05"}
        without_ts = Utterance(2, Speaker("Bob"), "hi")
        assert without_ts.to_dict()["timestamp"] is None


class TestMetadata:
    def test_to_dict_serialises_date(self) -> None:
        metadata = Metadata(title="Sync", date=date(2026, 6, 27), extra={"team": "Apollo"})
        result = metadata.to_dict()
        assert result["title"] == "Sync"
        assert result["date"] == "2026-06-27"
        assert result["extra"] == {"team": "Apollo"}

    def test_defaults(self) -> None:
        metadata = Metadata()
        assert metadata.to_dict() == {
            "title": None,
            "date": None,
            "source_path": None,
            "source_format": None,
            "extra": {},
        }


class TestMeeting:
    def _meeting(self) -> Meeting:
        alice, bob = Speaker("Alice"), Speaker("Bob")
        return Meeting(
            utterances=(
                Utterance(0, alice, "hello", Timestamp.from_seconds(10)),
                Utterance(1, bob, "hi"),
                Utterance(2, alice, "bye", Timestamp.from_seconds(30)),
            ),
            metadata=Metadata(title="Sync"),
        )

    def test_speakers_in_first_appearance_order(self) -> None:
        assert self._meeting().speakers == ("Alice", "Bob")

    def test_start_and_end(self) -> None:
        meeting = self._meeting()
        assert meeting.start == Timestamp.from_seconds(10)
        assert meeting.end == Timestamp.from_seconds(30)

    def test_start_end_none_without_timestamps(self) -> None:
        meeting = Meeting(utterances=(Utterance(0, Speaker("A"), "x"),))
        assert meeting.start is None
        assert meeting.end is None

    def test_len_and_iter(self) -> None:
        meeting = self._meeting()
        assert len(meeting) == 3
        assert [u.index for u in meeting] == [0, 1, 2]

    def test_to_dict_structure(self) -> None:
        result = self._meeting().to_dict()
        assert result["speakers"] == ["Alice", "Bob"]
        assert len(result["utterances"]) == 3
        assert result["metadata"]["title"] == "Sync"

    def test_empty_meeting_defaults(self) -> None:
        meeting = Meeting()
        assert len(meeting) == 0
        assert meeting.speakers == ()
