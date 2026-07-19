from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

_MODELS_ROOT = Path(__file__).resolve().parents[2] / "models"


@dataclass
class RawSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionInfo:
    language: str
    duration: float


class TranscriptionModel(Protocol):
    def transcribe(self, audio_path: Path) -> tuple[Iterable[RawSegment], TranscriptionInfo]: ...


class FasterWhisperTranscriptionModel:
    def __init__(self, model_size: str = "large-v3-turbo", device: str = "cpu", compute_type: str = "int8"):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = None

    def transcribe(self, audio_path: Path) -> tuple[Iterable[RawSegment], TranscriptionInfo]:
        from faster_whisper import WhisperModel

        if self._model is None:
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
                download_root=str(_MODELS_ROOT),
            )

        segments, info = self._model.transcribe(str(audio_path))
        raw_segments = (RawSegment(start=s.start, end=s.end, text=s.text) for s in segments)
        return raw_segments, TranscriptionInfo(language=info.language, duration=info.duration)
