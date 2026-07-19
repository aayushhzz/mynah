from __future__ import annotations

import pytest

from conftest import FakeOllamaClient
from summarization.formatter import render_actions_markdown, render_summary_markdown
from summarization.ollama_client import OllamaError, SubprocessOllamaClient
from summarization.parser import parse_llm_response
from summarization.summarizer import EmptyTranscriptError, Summarizer

WELL_FORMED_RESPONSE = """\
Executive Summary
The team discussed Q3 roadmap and agreed on priorities.

Decisions
- Ship feature X by end of month
- Deprioritize feature Y

Action Items
- Draft the API spec (Owner: Alice, Due: Friday)
- Review the spec (Owner: Bob)

Risks
- Vendor delay could slip the timeline

Open Questions
- Do we need a fallback provider?
"""


def test_empty_transcript_raises():
    client = FakeOllamaClient(canned_response="irrelevant")
    summarizer = Summarizer(client)

    with pytest.raises(EmptyTranscriptError):
        summarizer.summarize("   ")


def test_well_formed_response_parses_all_five_sections():
    client = FakeOllamaClient(canned_response=WELL_FORMED_RESPONSE)
    summarizer = Summarizer(client)

    result = summarizer.summarize("some transcript text")

    assert "Q3 roadmap" in result.executive_summary
    assert result.decisions == ["Ship feature X by end of month", "Deprioritize feature Y"]
    assert len(result.action_items) == 2
    assert result.action_items[0].description == "Draft the API spec"
    assert result.action_items[0].owner == "Alice"
    assert result.action_items[0].due == "Friday"
    assert result.risks == ["Vendor delay could slip the timeline"]
    assert result.open_questions == ["Do we need a fallback provider?"]
    assert result.raw_response == WELL_FORMED_RESPONSE


def test_missing_section_returns_empty_list_no_exception():
    response = """\
Executive Summary
All good here.

Decisions
- Keep going
"""
    result = parse_llm_response(response)

    assert result.executive_summary == "All good here."
    assert result.decisions == ["Keep going"]
    assert result.risks == []
    assert result.open_questions == []
    assert result.action_items == []


def test_fully_unstructured_response_falls_back_to_raw_text():
    raw = "This is just a blob of unstructured text with no headings at all."
    result = parse_llm_response(raw)

    assert result.executive_summary == raw
    assert result.decisions == []
    assert result.action_items == []
    assert result.risks == []
    assert result.open_questions == []
    assert result.raw_response == raw


def test_action_items_with_and_without_owner_and_due():
    response = """\
Action Items
- Do the thing (Owner: Alice, Due: Monday)
- Do another thing (Owner: Bob)
- Do a third thing
"""
    result = parse_llm_response(response)

    assert result.action_items[0].description == "Do the thing"
    assert result.action_items[0].owner == "Alice"
    assert result.action_items[0].due == "Monday"

    assert result.action_items[1].description == "Do another thing"
    assert result.action_items[1].owner == "Bob"
    assert result.action_items[1].due is None

    assert result.action_items[2].description == "Do a third thing"
    assert result.action_items[2].owner is None
    assert result.action_items[2].due is None


def test_duplicate_headings_concatenate_rather_than_overwrite():
    response = """\
Risks
- Risk one

Risks
- Risk two
"""
    result = parse_llm_response(response)

    assert result.risks == ["Risk one", "Risk two"]


def test_subprocess_client_builds_correct_command(fake_sync_command_runner):
    fake_sync_command_runner.stdout = "some summary"
    client = SubprocessOllamaClient(fake_sync_command_runner)

    output = client.generate("qwen3:4b-instruct", "transcript text")

    assert fake_sync_command_runner.calls == [["ollama", "run", "qwen3:4b-instruct"]]
    assert fake_sync_command_runner.inputs_received == ["transcript text"]
    assert output == "some summary"


def test_subprocess_client_raises_ollama_error_on_failure(fake_sync_command_runner):
    fake_sync_command_runner.returncode = 1
    fake_sync_command_runner.stderr = "model not found"
    client = SubprocessOllamaClient(fake_sync_command_runner)

    with pytest.raises(OllamaError):
        client.generate("qwen3:4b-instruct", "transcript text")


def test_render_summary_markdown():
    client = FakeOllamaClient(canned_response=WELL_FORMED_RESPONSE)
    summarizer = Summarizer(client)
    result = summarizer.summarize("transcript")

    markdown = render_summary_markdown(result)

    assert "# Executive Summary" in markdown
    assert "## Decisions" in markdown
    assert "Ship feature X by end of month" in markdown


def test_render_actions_markdown():
    client = FakeOllamaClient(canned_response=WELL_FORMED_RESPONSE)
    summarizer = Summarizer(client)
    result = summarizer.summarize("transcript")

    markdown = render_actions_markdown(result)

    assert "# Action Items" in markdown
    assert "Draft the API spec (Owner: Alice, Due: Friday)" in markdown
    assert "Review the spec (Owner: Bob)" in markdown


def test_summarization_integration():
    client = FakeOllamaClient(canned_response=WELL_FORMED_RESPONSE)
    summarizer = Summarizer(client)

    result = summarizer.summarize("realistic transcript text")

    assert result.executive_summary
    assert result.decisions
    assert result.action_items
    assert result.risks
    assert result.open_questions

    summary_md = render_summary_markdown(result)
    actions_md = render_actions_markdown(result)

    assert summary_md.strip()
    assert actions_md.strip()
