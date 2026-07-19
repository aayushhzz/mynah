from __future__ import annotations

from common.types import SummaryResult
from summarization.ollama_client import OllamaClient
from summarization.parser import parse_llm_response

_PROMPT_TEMPLATE = """\
Summarize the following meeting transcript. Respond using exactly these five \
section headings, each on its own line, in this order: Executive Summary, \
Decisions, Action Items, Risks, Open Questions. Under each heading, use a \
short paragraph (Executive Summary) or a bullet list (all other sections). \
If a section has nothing to report, leave it empty but still include its \
heading. For each action item, name the owner and due date if mentioned, \
formatted as "- <description> (Owner: <name>, Due: <date>)". Do not add any \
other headings or commentary.

Transcript:
{transcript}
"""


class EmptyTranscriptError(Exception):
    pass


class Summarizer:
    def __init__(self, client: OllamaClient, model: str = "qwen3:4b-instruct"):
        self._client = client
        self._model = model

    def summarize(self, transcript_text: str) -> SummaryResult:
        if not transcript_text.strip():
            raise EmptyTranscriptError("Cannot summarize an empty transcript")

        prompt = _PROMPT_TEMPLATE.format(transcript=transcript_text)
        raw_response = self._client.generate(self._model, prompt)
        return parse_llm_response(raw_response)
