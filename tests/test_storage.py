from __future__ import annotations

import threading
from datetime import date
from pathlib import Path

import pytest

from common.types import Meeting
from storage.id_generator import next_meeting_id, reserve_meeting_folder
from storage.meeting_store import MeetingStore, SourceFileNotFoundError


def test_folder_structure_created_correctly(tmp_path):
    folder = reserve_meeting_folder(tmp_path, when=date(2026, 7, 19))
    assert folder == tmp_path / "2026" / "07" / "meeting-001"
    assert folder.exists()


def test_id_increments_with_existing_meetings(tmp_path):
    (tmp_path / "2026" / "07" / "meeting-001").mkdir(parents=True)
    (tmp_path / "2026" / "07" / "meeting-002").mkdir(parents=True)

    assert next_meeting_id(tmp_path) == 3


def test_skips_id_already_taken_on_disk(tmp_path):
    (tmp_path / "2026" / "07" / "meeting-001").mkdir(parents=True)

    folder = reserve_meeting_folder(tmp_path, when=date(2026, 7, 19))

    assert folder == tmp_path / "2026" / "07" / "meeting-002"


def test_concurrent_creation_produces_distinct_folders(tmp_path):
    num_threads = 8
    barrier = threading.Barrier(num_threads)
    results: list[Path] = []
    results_lock = threading.Lock()

    def create():
        barrier.wait()
        folder = reserve_meeting_folder(tmp_path, when=date(2026, 7, 19))
        with results_lock:
            results.append(folder)

    threads = [threading.Thread(target=create) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(results)) == num_threads


def test_month_year_rollover_with_injectable_when(tmp_path):
    folder = reserve_meeting_folder(tmp_path, when=date(2025, 12, 31))
    assert folder == tmp_path / "2025" / "12" / "meeting-001"


def test_save_audio_moves_file_in(tmp_path):
    store = MeetingStore(tmp_path)
    handle = store.create_meeting(when=date(2026, 7, 19))
    source = tmp_path / "recording.wav"
    source.write_bytes(b"audio-data")

    dest = handle.save_audio(source)

    assert dest == handle.folder / "recording.wav"
    assert dest.read_bytes() == b"audio-data"
    assert not source.exists()


def test_save_audio_raises_if_source_missing(tmp_path):
    store = MeetingStore(tmp_path)
    handle = store.create_meeting(when=date(2026, 7, 19))

    with pytest.raises(SourceFileNotFoundError):
        handle.save_audio(tmp_path / "missing.wav")


def test_save_transcript_summary_actions_write_expected_content(tmp_path):
    store = MeetingStore(tmp_path)
    handle = store.create_meeting(when=date(2026, 7, 19))

    handle.save_transcript("# Transcript")
    handle.save_summary("# Summary")
    handle.save_actions("# Actions")

    assert (handle.folder / "transcript.md").read_text() == "# Transcript"
    assert (handle.folder / "summary.md").read_text() == "# Summary"
    assert (handle.folder / "actions.md").read_text() == "# Actions"


def test_save_and_load_metadata_round_trips_exactly(tmp_path):
    store = MeetingStore(tmp_path)
    handle = store.create_meeting(when=date(2026, 7, 19))
    meeting = Meeting(
        id="meeting-001",
        title="Sprint Planning",
        date=date(2026, 7, 19),
        duration_seconds=1800.0,
        language="en",
        participants=["Alice", "Bob"],
        topics=["roadmap", "Q3"],
        status="recorded",
        folder=handle.folder,
    )

    handle.save_metadata(meeting)
    loaded = handle.load_metadata()

    assert loaded == meeting


def test_repeated_saves_overwrite_not_duplicate(tmp_path):
    store = MeetingStore(tmp_path)
    handle = store.create_meeting(when=date(2026, 7, 19))

    handle.save_transcript("first version")
    handle.save_transcript("second version")

    assert (handle.folder / "transcript.md").read_text() == "second version"
    assert len(list(handle.folder.glob("transcript*"))) == 1


def test_storage_integration(tmp_path):
    store = MeetingStore(tmp_path)
    handle = store.create_meeting(when=date(2026, 7, 19))

    audio_source = tmp_path / "recording.wav"
    audio_source.write_bytes(b"audio-data")
    handle.save_audio(audio_source)
    handle.save_transcript("# Transcript")
    handle.save_summary("# Summary")
    handle.save_actions("# Actions")
    meeting = Meeting(
        id="meeting-001",
        title="Sprint Planning",
        date=date(2026, 7, 19),
        duration_seconds=1800.0,
        language="en",
        participants=["Alice"],
        topics=["roadmap"],
        status="recorded",
        folder=handle.folder,
    )
    handle.save_metadata(meeting)

    expected_files = {"recording.wav", "transcript.md", "summary.md", "actions.md", "metadata.json"}
    actual_files = {p.name for p in handle.folder.iterdir()}
    assert actual_files == expected_files

    loaded = handle.load_metadata()
    assert loaded == meeting
