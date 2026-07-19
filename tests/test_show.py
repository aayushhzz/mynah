from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cli import _read_section_content, _select_last_meeting, prompt_section_choice
from common.types import Meeting


def _make_meeting(id: str, folder: Path) -> Meeting:
    return Meeting(
        id=id,
        title=f"Meeting {id}",
        date=date(2026, 7, 19),
        duration_seconds=60.0,
        language="en",
        participants=[],
        topics=[],
        status="summarized",
        folder=folder,
    )


def test_select_last_meeting_returns_highest_numeric_id(tmp_path):
    meetings = [
        _make_meeting("meeting-001", tmp_path / "1"),
        _make_meeting("meeting-010", tmp_path / "10"),
        _make_meeting("meeting-002", tmp_path / "2"),
    ]

    result = _select_last_meeting(meetings)

    assert result.id == "meeting-010"


def test_select_last_meeting_returns_none_for_empty_list():
    assert _select_last_meeting([]) is None


def test_read_section_content_reads_summary_file(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "summary.md").write_text("# Executive Summary\nAll good.")
    meeting = _make_meeting("meeting-001", tmp_path)

    content = _read_section_content(meeting, "summary")

    assert content == "# Executive Summary\nAll good."


def test_read_section_content_reads_transcript_file(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "transcript.md").write_text("[00:00] Speaker 1: Hello")
    meeting = _make_meeting("meeting-001", tmp_path)

    content = _read_section_content(meeting, "transcript")

    assert content == "[00:00] Speaker 1: Hello"


def test_read_section_content_raises_when_file_missing(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    meeting = _make_meeting("meeting-001", tmp_path)

    with pytest.raises(FileNotFoundError):
        _read_section_content(meeting, "summary")


def test_prompt_section_choice_accepts_numeric_1():
    inputs = iter(["1"])
    result = prompt_section_choice(input_func=lambda _: next(inputs))
    assert result == "summary"


def test_prompt_section_choice_accepts_numeric_2():
    inputs = iter(["2"])
    result = prompt_section_choice(input_func=lambda _: next(inputs))
    assert result == "transcript"


def test_prompt_section_choice_accepts_word_aliases():
    inputs = iter(["transcript"])
    result = prompt_section_choice(input_func=lambda _: next(inputs))
    assert result == "transcript"

    inputs2 = iter(["summary"])
    result2 = prompt_section_choice(input_func=lambda _: next(inputs2))
    assert result2 == "summary"


def test_prompt_section_choice_accepts_short_aliases():
    inputs = iter(["s"])
    assert prompt_section_choice(input_func=lambda _: next(inputs)) == "summary"

    inputs2 = iter(["t"])
    assert prompt_section_choice(input_func=lambda _: next(inputs2)) == "transcript"


def test_prompt_section_choice_reprompts_on_invalid_input():
    inputs = iter(["garbage", "", "3", "2"])
    result = prompt_section_choice(input_func=lambda _: next(inputs))
    assert result == "transcript"
