from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

from common.process import SubprocessSyncCommandRunner
from common.types import Meeting
from config.settings import (
    DB_PATH,
    MEETINGS_ROOT,
    OLLAMA_MODEL,
    RECORDING_SOURCES_ROOT,
    RECORDING_STATE_PATH,
    SYSTEM_AUDIO_RECORDER_BINARY,
    WHISPER_MODEL_SIZE,
)
from kb.database import init_db
from kb.indexer import MeetingIndexer
from recording.background import (
    NoActiveRecordingError,
    OSDetachedProcessLauncher,
    OSProcessController,
    RecordingAlreadyActiveError,
    RecordingStateStore,
)
from recording.mixer import AudioMixingError, mix_audio
from recording.multi_source import MultiSourceRecorder, NoSourcesStartedError, SourceSpec
from recording.recorder import EmptyRecordingError, build_ffmpeg_record_cmd
from search.keyword_search import KeywordSearch, SearchIndexer, init_search_index
from storage.meeting_store import MeetingStore
from summarization.formatter import render_actions_markdown, render_summary_markdown
from summarization.ollama_client import SubprocessOllamaClient
from summarization.summarizer import Summarizer
from transcription.formatter import segments_to_markdown, transcript_to_plain_text
from transcription.transcriber import Transcriber
from transcription.whisper_model import FasterWhisperTranscriptionModel


_COLOR_CYAN = "\033[36m"
_COLOR_YELLOW = "\033[33m"
_COLOR_BOLD = "\033[1m"
_COLOR_RESET = "\033[0m"

_MEETING_ID_PATTERN = re.compile(r"(\d+)$")


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _colorize(text: str, *codes: str) -> str:
    if not _supports_color():
        return text
    return "".join(codes) + text + _COLOR_RESET


def _print_tip(message: str) -> None:
    print(_colorize(f"Tip: {message}", _COLOR_YELLOW))


def _print_heading(text: str) -> None:
    print(_colorize(text, _COLOR_BOLD, _COLOR_CYAN))


def _open_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = init_db(DB_PATH)
    init_search_index(connection)
    return connection


def _process_audio(audio_path: Path, title: str, raw_sources: list[tuple[str, Path]] | None = None) -> Meeting:
    sync_runner = SubprocessSyncCommandRunner()

    print(f"Transcribing {audio_path} with faster-whisper ({WHISPER_MODEL_SIZE})...")
    model = FasterWhisperTranscriptionModel(model_size=WHISPER_MODEL_SIZE)
    transcriber = Transcriber(model)
    transcript_result = transcriber.transcribe(audio_path)
    transcript_markdown = segments_to_markdown(transcript_result)
    transcript_text = transcript_to_plain_text(transcript_result)

    print(f"Summarizing with Ollama ({OLLAMA_MODEL})...")
    ollama_client = SubprocessOllamaClient(sync_runner)
    summarizer = Summarizer(ollama_client, model=OLLAMA_MODEL)
    summary_result = summarizer.summarize(transcript_text)
    summary_markdown = render_summary_markdown(summary_result)
    actions_markdown = render_actions_markdown(summary_result)

    print("Saving to local storage...")
    store = MeetingStore(MEETINGS_ROOT)
    handle = store.create_meeting()
    handle.save_audio(audio_path)
    handle.save_transcript(transcript_markdown)
    handle.save_summary(summary_markdown)
    handle.save_actions(actions_markdown)

    for source_name, source_path in raw_sources or []:
        if source_path.exists():
            shutil.move(str(source_path), str(handle.folder / f"source_{source_name}.wav"))

    meeting = Meeting(
        id=handle.folder.name,
        title=title,
        date=date.today(),
        duration_seconds=transcript_result.duration_seconds,
        language=transcript_result.language,
        participants=[],
        topics=[],
        status="summarized",
        folder=handle.folder,
    )
    handle.save_metadata(meeting)

    print("Indexing...")
    connection = _open_connection()
    MeetingIndexer(connection).index_meeting(meeting)
    SearchIndexer(connection).index_content(
        meeting_id=meeting.id,
        title=meeting.title,
        transcript_text=transcript_text,
        summary_text=summary_result.raw_response,
        topics="",
    )
    connection.close()

    print(f"Done: {meeting.folder}")
    return meeting


def _recording_sources() -> list[SourceSpec]:
    return [
        SourceSpec(
            name="mic",
            build_cmd=lambda output_path: build_ffmpeg_record_cmd("ffmpeg", ":0", output_path),
        ),
        SourceSpec(
            name="system_audio",
            build_cmd=lambda output_path: [str(SYSTEM_AUDIO_RECORDER_BINARY), str(output_path)],
        ),
    ]


def _multi_source_recorder() -> MultiSourceRecorder:
    return MultiSourceRecorder(
        OSDetachedProcessLauncher(),
        OSProcessController(),
        RecordingStateStore(RECORDING_STATE_PATH),
        _recording_sources(),
    )


def cmd_record(args: argparse.Namespace) -> None:
    recorder = _multi_source_recorder()

    if recorder.is_recording():
        print("A recording is already in progress", file=sys.stderr)
        sys.exit(1)

    RECORDING_SOURCES_ROOT.mkdir(parents=True, exist_ok=True)
    sources_dir = Path(tempfile.mkdtemp(prefix="meeting-sources-", dir=str(RECORDING_SOURCES_ROOT)))

    try:
        warnings = recorder.start(sources_dir, title=args.title)
    except (RecordingAlreadyActiveError, NoSourcesStartedError) as exc:
        shutil.rmtree(sources_dir, ignore_errors=True)
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    print(f"Recording started (sources in {sources_dir}).")
    print("Run 'mynah stop' when you're done.")


def cmd_stop(args: argparse.Namespace) -> None:
    recorder = _multi_source_recorder()
    state_store = RecordingStateStore(RECORDING_STATE_PATH)

    sources_dir = None
    if state_store.exists():
        try:
            state = state_store.load()
            if state.sources:
                sources_dir = Path(state.sources[0].output_path).parent
        except NoActiveRecordingError:
            pass

    print("Stopping recording...")
    try:
        try:
            sources, title, warnings = recorder.stop()
        except (NoActiveRecordingError, EmptyRecordingError) as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)

        if len(sources) == 1:
            mixed_path = sources[0][1]
        else:
            sync_runner = SubprocessSyncCommandRunner()
            mixed_path = sources[0][1].parent / "mixed.wav"
            print(f"Mixing {len(sources)} audio sources with loudness normalization...")
            try:
                mix_audio(sync_runner, [path for _, path in sources], mixed_path)
            except AudioMixingError as exc:
                print(str(exc), file=sys.stderr)
                sys.exit(1)

        _process_audio(mixed_path, title=title or mixed_path.stem, raw_sources=sources)
    finally:
        if sources_dir is not None:
            shutil.rmtree(sources_dir, ignore_errors=True)


def cmd_process(args: argparse.Namespace) -> None:
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)
    _process_audio(audio_path, title=args.title or audio_path.stem)


def cmd_list(args: argparse.Namespace) -> None:
    connection = _open_connection()
    meetings = MeetingIndexer(connection).list_meetings(status=args.status)
    connection.close()

    if not meetings:
        print("No meetings found.")
        return

    for meeting in meetings:
        print(f"{meeting.id}  {meeting.date}  [{meeting.status}]  {meeting.title}")


def cmd_search(args: argparse.Namespace) -> None:
    connection = _open_connection()
    results = KeywordSearch(connection).search(args.query, limit=args.limit)
    connection.close()

    if not results:
        print("No results.")
        return

    for result in results:
        print(f"{result.meeting_id}  {result.title}  ({result.score:.2f})")
        print(f"  {result.snippet}")


_SECTION_FILENAMES = {
    "summary": "summary.md",
    "transcript": "transcript.md",
}

_SECTION_ALIASES = {
    "1": "summary",
    "2": "transcript",
    "s": "summary",
    "summary": "summary",
    "t": "transcript",
    "transcript": "transcript",
}


def _select_last_meeting(meetings: list[Meeting]) -> Meeting | None:
    def sort_key(meeting: Meeting):
        match = _MEETING_ID_PATTERN.search(meeting.id)
        return int(match.group(1)) if match else -1

    if not meetings:
        return None
    return max(meetings, key=sort_key)


def _read_section_content(meeting: Meeting, section: str) -> str:
    path = meeting.folder / _SECTION_FILENAMES[section]
    if not path.exists():
        raise FileNotFoundError(f"{section.capitalize()} not found for {meeting.id}: {path}")
    return path.read_text()


def prompt_section_choice(input_func=input) -> str:
    while True:
        raw = input_func("Show [1] Summary or [2] Transcript? ").strip().lower()
        if raw in _SECTION_ALIASES:
            return _SECTION_ALIASES[raw]
        print("Please enter 1/summary or 2/transcript.")


def cmd_show(args: argparse.Namespace) -> None:
    connection = _open_connection()
    indexer = MeetingIndexer(connection)

    if args.meeting_id:
        meeting = indexer.get_meeting(args.meeting_id)
        connection.close()
        if meeting is None:
            print(f"No meeting found with id: {args.meeting_id}", file=sys.stderr)
            sys.exit(1)
    else:
        meetings = indexer.list_meetings()
        connection.close()
        meeting = _select_last_meeting(meetings)
        if meeting is None:
            print("No meetings found.")
            return

    section = args.section or prompt_section_choice()

    try:
        content = _read_section_content(meeting, section)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    _print_heading(f"{section.capitalize()} — {meeting.title} ({meeting.id}, {meeting.date})")
    print()
    print(content)

    if not args.meeting_id:
        print()
        _print_tip(f"use 'mynah show {meeting.id}' to view a specific meeting.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mynah", description="Mynah — your local AI meeting assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser(
        "record", help="Start recording mic + system audio in the background"
    )
    record_parser.add_argument("--title", default=None, help="Meeting title (default: derived from filename)")
    record_parser.set_defaults(func=cmd_record)

    stop_parser = subparsers.add_parser(
        "stop", help="Stop the active recording and transcribe/summarize/index it"
    )
    stop_parser.set_defaults(func=cmd_stop)

    process_parser = subparsers.add_parser("process", help="Process an existing audio file")
    process_parser.add_argument("audio_file", help="Path to a WAV audio file")
    process_parser.add_argument("--title", default=None, help="Meeting title (default: derived from filename)")
    process_parser.set_defaults(func=cmd_process)

    list_parser = subparsers.add_parser("list", help="List indexed meetings")
    list_parser.add_argument("--status", default=None, help="Filter by status")
    list_parser.set_defaults(func=cmd_list)

    search_parser = subparsers.add_parser("search", help="Keyword search across meetings")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    search_parser.set_defaults(func=cmd_search)

    show_parser = subparsers.add_parser(
        "show", help="Show a meeting's summary or transcript (defaults to the most recent meeting)"
    )
    show_parser.add_argument("meeting_id", nargs="?", default=None, help="Meeting id, e.g. meeting-003")
    show_parser.add_argument(
        "--section", choices=["summary", "transcript"], default=None, help="Skip the interactive prompt"
    )
    show_parser.set_defaults(func=cmd_show)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
