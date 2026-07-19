from __future__ import annotations

from pathlib import Path

from common.types import Segment, TranscriptResult
from transcription.speaker_labeling import SingleSpeakerStrategy, SpeakerLabelStrategy
from transcription.whisper_model import TranscriptionModel


class EmptyTranscriptionError(Exception):
    pass


class Transcriber:
    def __init__(self, model: TranscriptionModel, speaker_strategy: SpeakerLabelStrategy | None = None):
        self._model = model
        self._speaker_strategy = speaker_strategy or SingleSpeakerStrategy()

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        raw_segments, info = self._model.transcribe(audio_path)
        raw_segments = sorted(raw_segments, key=lambda s: s.start)

        if not raw_segments:
            raise EmptyTranscriptionError(f"No segments produced for {audio_path}")

        labels = self._speaker_strategy.label(raw_segments)
        segments = [
            Segment(start=raw.start, end=raw.end, text=raw.text, speaker=label)
            for raw, label in zip(raw_segments, labels)
        ]

        return TranscriptResult(
            segments=segments,
            language=info.language,
            audio_path=Path(audio_path),
            duration_seconds=info.duration,
        )
