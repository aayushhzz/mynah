from __future__ import annotations

from datetime import date

import pytest

from common.process import SubprocessCommandRunner, SubprocessSyncCommandRunner
from config.settings import OLLAMA_MODEL, WHISPER_MODEL_SIZE
from kb.database import init_db
from kb.indexer import MeetingIndexer
from search.keyword_search import KeywordSearch, SearchIndexer, init_search_index
from storage.meeting_store import MeetingStore
from summarization.formatter import render_actions_markdown, render_summary_markdown
from summarization.ollama_client import SubprocessOllamaClient
from summarization.summarizer import Summarizer
from transcription.formatter import segments_to_markdown, transcript_to_plain_text
from transcription.transcriber import Transcriber
from transcription.whisper_model import FasterWhisperTranscriptionModel

pytestmark = pytest.mark.e2e


def test_end_to_end_pipeline_with_real_models(tmp_path):
    audio_path = tmp_path / "synthetic.wav"
    command_runner = SubprocessCommandRunner()

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(audio_path),
    ]
    handle = command_runner.start(cmd)
    handle.wait()
    assert audio_path.exists() and audio_path.stat().st_size > 0

    model = FasterWhisperTranscriptionModel(model_size=WHISPER_MODEL_SIZE)
    transcriber = Transcriber(model)
    transcript_result = transcriber.transcribe(audio_path)

    assert len(transcript_result.segments) >= 1

    fake_speech_text = (
        "We agreed to ship the new dashboard feature by Friday. "
        "The team decided to deprioritize the legacy export tool. "
        "Action item: Alice will draft the API spec by Monday. "
        "Risk: the vendor integration could slip the timeline. "
        "Open question: do we need a fallback data provider?"
    )
    transcript_text = transcript_to_plain_text(transcript_result) or fake_speech_text
    transcript_markdown = segments_to_markdown(transcript_result)

    sync_runner = SubprocessSyncCommandRunner()
    ollama_client = SubprocessOllamaClient(sync_runner)
    summarizer = Summarizer(ollama_client, model=OLLAMA_MODEL)
    summary_result = summarizer.summarize(fake_speech_text)

    assert summary_result.raw_response.strip()

    summary_markdown = render_summary_markdown(summary_result)
    actions_markdown = render_actions_markdown(summary_result)

    store = MeetingStore(tmp_path / "Meetings")
    handle = store.create_meeting(when=date.today())
    handle.save_audio(audio_path)
    handle.save_transcript(transcript_markdown)
    handle.save_summary(summary_markdown)
    handle.save_actions(actions_markdown)

    from common.types import Meeting

    meeting = Meeting(
        id=handle.folder.name,
        title="E2E Smoke Test Meeting",
        date=date.today(),
        duration_seconds=transcript_result.duration_seconds,
        language=transcript_result.language,
        participants=[],
        topics=["dashboard", "vendor integration"],
        status="indexed",
        folder=handle.folder,
    )
    handle.save_metadata(meeting)

    for expected_file in ["transcript.md", "summary.md", "actions.md", "metadata.json"]:
        path = handle.folder / expected_file
        assert path.exists() and path.stat().st_size > 0

    db_path = tmp_path / "meetings.sqlite3"
    connection = init_db(db_path)
    init_search_index(connection)

    meeting_indexer = MeetingIndexer(connection)
    meeting_indexer.index_meeting(meeting)

    search_indexer = SearchIndexer(connection)
    search_indexer.index_content(
        meeting_id=meeting.id,
        title=meeting.title,
        transcript_text=fake_speech_text,
        summary_text=summary_result.raw_response,
        topics=" ".join(meeting.topics),
    )

    search = KeywordSearch(connection)
    results = search.search("dashboard")

    assert any(r.meeting_id == meeting.id for r in results)
