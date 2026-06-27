"""Unit tests for the transcript parser."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from meeting_memory.exceptions import MalformedTranscriptError
from meeting_memory.io import RawTranscript
from meeting_memory.parser import MeetingParser, parse_file, parse_json, parse_text


class TestParseText:
    def test_simple_single_speaker(self) -> None:
        meeting = parse_text("Alice: Hello world")
        assert len(meeting) == 1
        assert meeting.utterances[0].speaker.name == "Alice"
        assert meeting.utterances[0].text == "Hello world"
        assert meeting.utterances[0].timestamp is None

    def test_multiple_speakers_ordering(self) -> None:
        meeting = parse_text("Alice: hi\nBob: hey\nAlice: bye")
        assert meeting.speakers == ("Alice", "Bob")
        assert [u.index for u in meeting] == [0, 1, 2]
        assert [u.speaker.name for u in meeting] == ["Alice", "Bob", "Alice"]

    def test_leading_timestamp(self) -> None:
        meeting = parse_text("[00:01:05] Alice: hi")
        assert meeting.utterances[0].timestamp is not None
        assert meeting.utterances[0].timestamp.label == "00:01:05"

    def test_trailing_bracketed_timestamp(self) -> None:
        meeting = parse_text("Bob [00:00:10]: hey there")
        assert meeting.utterances[0].speaker.name == "Bob"
        assert meeting.utterances[0].timestamp is not None
        assert meeting.utterances[0].timestamp.label == "00:00:10"

    def test_trailing_plain_timestamp(self) -> None:
        meeting = parse_text("Carol 00:01:00: plain")
        assert meeting.utterances[0].speaker.name == "Carol"
        assert meeting.utterances[0].timestamp is not None
        assert meeting.utterances[0].timestamp.label == "00:01:00"

    def test_timestamp_inside_text_not_confused(self) -> None:
        meeting = parse_text("Alice: meet at 10:30 tomorrow")
        assert meeting.utterances[0].text == "meet at 10:30 tomorrow"
        assert meeting.utterances[0].timestamp is None

    def test_continuation_lines_merge(self) -> None:
        meeting = parse_text("Alice: first line\nstill alice\nBob: hello")
        assert len(meeting) == 2
        assert meeting.utterances[0].text == "first line still alice"
        assert meeting.utterances[1].speaker.name == "Bob"

    def test_blank_lines_ignored(self) -> None:
        meeting = parse_text("Alice: hi\n\n\nBob: hey")
        assert len(meeting) == 2

    def test_crlf_and_whitespace_normalized(self) -> None:
        meeting = parse_text("Alice:   hello   world  \r\nBob:\they\r\n")
        assert meeting.utterances[0].text == "hello world"
        assert meeting.utterances[1].text == "hey"

    def test_speaker_alias_recorded(self) -> None:
        meeting = parse_text("**Alice**: hi\nAlice: bye")
        assert meeting.speakers == ("Alice",)
        alice = meeting.utterances[0].speaker
        assert "**Alice**" in alice.aliases

    def test_front_matter_metadata(self) -> None:
        text = "---\ntitle: Weekly Sync\ndate: 2026-06-27\nteam: Apollo\n---\nAlice: hi"
        meeting = parse_text(text)
        assert meeting.metadata.title == "Weekly Sync"
        assert meeting.metadata.date == date(2026, 6, 27)
        assert meeting.metadata.extra == {"team": "Apollo"}
        assert len(meeting) == 1

    def test_front_matter_unterminated(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="Unterminated"):
            parse_text("---\ntitle: X\nAlice: hi")

    def test_front_matter_invalid_line(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="front-matter"):
            parse_text("---\nnot a pair\n---\nAlice: hi")

    def test_front_matter_invalid_date(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="Invalid date"):
            parse_text("---\ndate: 27-06-2026\n---\nAlice: hi")

    def test_malformed_line_without_speaker(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="Line 1"):
            parse_text("just some narration with no speaker label here at all today")

    def test_empty_text_yields_empty_meeting(self) -> None:
        meeting = parse_text("")
        assert len(meeting) == 0

    def test_empty_head_colon_treated_as_continuation(self) -> None:
        meeting = parse_text("Alice: hi\n: stray fragment")
        assert len(meeting) == 1
        assert meeting.utterances[0].text == "hi : stray fragment"

    def test_overlong_head_treated_as_continuation(self) -> None:
        long_head = "word " * 20
        meeting = parse_text(f"Alice: hi\n{long_head}: more")
        assert len(meeting) == 1
        assert meeting.utterances[0].text.startswith("hi word")

    def test_front_matter_blank_line_skipped(self) -> None:
        text = "---\ntitle: X\n\nteam: Apollo\n---\nAlice: hi"
        meeting = parse_text(text)
        assert meeting.metadata.title == "X"
        assert meeting.metadata.extra == {"team": "Apollo"}

    def test_empty_utterance_text(self) -> None:
        meeting = parse_text("Alice:\nBob: hi")
        assert meeting.utterances[0].text == ""
        assert meeting.utterances[1].text == "hi"

    def test_source_path_recorded(self) -> None:
        meeting = parse_text("Alice: hi", source_path="/tmp/x.txt")
        assert meeting.metadata.source_path == "/tmp/x.txt"
        assert meeting.metadata.source_format == "txt"


class TestParseJson:
    def test_object_with_utterances(self) -> None:
        data = {
            "title": "Standup",
            "date": "2026-01-02",
            "metadata": {"room": "A1"},
            "utterances": [
                {"speaker": "Carol", "text": "Morning", "timestamp": 65},
                {"name": "Dave", "content": "Hi", "time": "00:01:10"},
            ],
        }
        meeting = parse_json(data)
        assert meeting.metadata.title == "Standup"
        assert meeting.metadata.date == date(2026, 1, 2)
        assert meeting.metadata.extra == {"room": "A1"}
        assert meeting.speakers == ("Carol", "Dave")
        assert meeting.utterances[0].timestamp is not None
        assert meeting.utterances[0].timestamp.label == "00:01:05"
        assert meeting.utterances[1].timestamp is not None
        assert meeting.utterances[1].timestamp.label == "00:01:10"

    def test_bare_list_of_utterances(self) -> None:
        meeting = parse_json([{"speaker": "A", "text": "x"}])
        assert len(meeting) == 1
        assert meeting.metadata.title is None

    def test_object_without_optional_metadata(self) -> None:
        meeting = parse_json({"utterances": [{"speaker": "A", "text": "x"}]})
        assert meeting.metadata.title is None
        assert meeting.metadata.date is None
        assert meeting.metadata.extra == {}

    def test_metadata_none_values_skipped(self) -> None:
        data = {
            "utterances": [{"speaker": "A", "text": "x"}],
            "metadata": {"room": "A1", "host": None},
        }
        meeting = parse_json(data)
        assert meeting.metadata.extra == {"room": "A1"}

    def test_missing_utterances_key(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="missing 'utterances'"):
            parse_json({"title": "X"})

    def test_utterances_not_a_list(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="must be a JSON array"):
            parse_json({"utterances": {}})

    def test_top_level_wrong_type(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="object or array"):
            parse_json("a string")

    def test_item_not_object(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="#0 must be a JSON object"):
            parse_json([42])

    def test_item_missing_speaker(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="missing a speaker"):
            parse_json([{"text": "x"}])

    def test_item_missing_text(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="missing text"):
            parse_json([{"speaker": "A"}])

    def test_boolean_timestamp_rejected(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="invalid timestamp"):
            parse_json([{"speaker": "A", "text": "x", "timestamp": True}])

    def test_string_timestamp(self) -> None:
        meeting = parse_json([{"speaker": "A", "text": "x", "timestamp": "00:02:00"}])
        assert meeting.utterances[0].timestamp is not None
        assert meeting.utterances[0].timestamp.total_seconds == 120.0

    def test_invalid_date(self) -> None:
        with pytest.raises(MalformedTranscriptError, match="Invalid date"):
            parse_json({"date": "nonsense", "utterances": []})


class TestParseDispatch:
    def test_parse_text_via_raw(self) -> None:
        raw = RawTranscript(content="Alice: hi", source_format="txt", source_path="m.txt")
        meeting = MeetingParser().parse(raw)
        assert meeting.metadata.source_path == "m.txt"
        assert meeting.utterances[0].speaker.name == "Alice"

    def test_parse_json_via_raw(self) -> None:
        raw = RawTranscript(
            content={"utterances": [{"speaker": "A", "text": "x"}]},
            source_format="json",
            source_path="m.json",
        )
        meeting = MeetingParser().parse(raw)
        assert meeting.metadata.source_format == "json"

    def test_parse_unsupported_content_type(self) -> None:
        raw = RawTranscript(content=123, source_format="x", source_path="p")
        with pytest.raises(MalformedTranscriptError, match="Cannot parse"):
            MeetingParser().parse(raw)


class TestParseFile:
    def test_parse_txt_file(self, tmp_path: Path) -> None:
        path = tmp_path / "m.txt"
        path.write_text("[00:00:01] Alice: hi\nBob: hey", encoding="utf-8")
        meeting = parse_file(path)
        assert len(meeting) == 2
        assert meeting.metadata.source_path == str(path)

    def test_parse_json_file(self, tmp_path: Path) -> None:
        path = tmp_path / "m.json"
        path.write_text('{"utterances": [{"speaker": "A", "text": "x"}]}', encoding="utf-8")
        meeting = parse_file(path)
        assert len(meeting) == 1
