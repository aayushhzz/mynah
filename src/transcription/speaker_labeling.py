from __future__ import annotations

from typing import Protocol

from transcription.whisper_model import RawSegment


class SpeakerLabelStrategy(Protocol):
    def label(self, segments: list[RawSegment]) -> list[str]: ...


class SingleSpeakerStrategy:
    def label(self, segments: list[RawSegment]) -> list[str]:
        return ["Speaker 1"] * len(segments)
