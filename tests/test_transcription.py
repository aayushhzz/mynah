from __future__ import annotations

import pytest

from conftest import FakeTranscriptionModel
from transcription.formatter import segments_to_markdown, transcript_to_plain_text
from transcription.speaker_labeling import SingleSpeakerStrategy
from transcription.transcriber import EmptyTranscriptionError, Transcriber
from transcription.whisper_model import RawSegment, TranscriptionInfo


def test_labeled_segments_returned(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    model = FakeTranscriptionModel(
        canned_segments=[RawSegment(start=0.0, end=1.0, text="hello")],
        canned_info=TranscriptionInfo(language="en", duration=1.0),
    )
    transcriber = Transcriber(model)

    result = transcriber.transcribe(audio_path)

    assert len(result.segments) == 1
    assert result.segments[0].speaker == "Speaker 1"
    assert result.segments[0].text == "hello"
    assert result.language == "en"
    assert result.duration_seconds == 1.0
    assert result.audio_path == audio_path


def test_out_of_order_segments_get_sorted(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    model = FakeTranscriptionModel(
        canned_segments=[
            RawSegment(start=5.0, end=6.0, text="second"),
            RawSegment(start=0.0, end=1.0, text="first"),
        ],
    )
    transcriber = Transcriber(model)

    result = transcriber.transcribe(audio_path)

    assert [s.text for s in result.segments] == ["first", "second"]


def test_missing_audio_file_raises(tmp_path):
    model = FakeTranscriptionModel(canned_segments=[])
    transcriber = Transcriber(model)

    with pytest.raises(FileNotFoundError):
        transcriber.transcribe(tmp_path / "missing.wav")


def test_zero_segments_raises_empty_transcription_error(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    model = FakeTranscriptionModel(canned_segments=[])
    transcriber = Transcriber(model)

    with pytest.raises(EmptyTranscriptionError):
        transcriber.transcribe(audio_path)


def test_single_speaker_strategy_labels_all_speaker_1():
    strategy = SingleSpeakerStrategy()
    segments = [
        RawSegment(start=0.0, end=1.0, text="a"),
        RawSegment(start=1.0, end=2.0, text="b"),
    ]

    labels = strategy.label(segments)

    assert labels == ["Speaker 1", "Speaker 1"]


def test_segments_to_markdown_exact_match(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    model = FakeTranscriptionModel(
        canned_segments=[RawSegment(start=0.0, end=65.0, text="hello world")],
    )
    transcriber = Transcriber(model)
    result = transcriber.transcribe(audio_path)

    markdown = segments_to_markdown(result)

    assert markdown == "[00:00 - 01:05] Speaker 1: hello world"


def test_transcript_to_plain_text_exact_match(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    model = FakeTranscriptionModel(
        canned_segments=[
            RawSegment(start=0.0, end=1.0, text=" hello "),
            RawSegment(start=1.0, end=2.0, text="world"),
        ],
    )
    transcriber = Transcriber(model)
    result = transcriber.transcribe(audio_path)

    plain_text = transcript_to_plain_text(result)

    assert plain_text == "hello\nworld"


def test_transcription_integration(tmp_path):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake")
    model = FakeTranscriptionModel(
        canned_segments=[
            RawSegment(start=10.0, end=12.0, text="third, after a gap"),
            RawSegment(start=0.0, end=1.0, text="first"),
            RawSegment(start=1.0, end=2.0, text="second"),
        ],
        canned_info=TranscriptionInfo(language="en", duration=12.0),
    )
    transcriber = Transcriber(model)

    result = transcriber.transcribe(audio_path)

    assert [s.text for s in result.segments] == ["first", "second", "third, after a gap"]
    assert all(s.speaker == "Speaker 1" for s in result.segments)

    markdown = segments_to_markdown(result)
    plain_text = transcript_to_plain_text(result)

    assert "first" in markdown and "Speaker 1" in markdown
    assert plain_text == "first\nsecond\nthird, after a gap"
