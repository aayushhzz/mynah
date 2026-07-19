from __future__ import annotations

from common.types import TranscriptResult


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def segments_to_markdown(transcript: TranscriptResult) -> str:
    lines = []
    for segment in transcript.segments:
        start = _format_timestamp(segment.start)
        end = _format_timestamp(segment.end)
        lines.append(f"[{start} - {end}] {segment.speaker}: {segment.text}")
    return "\n".join(lines)


def transcript_to_plain_text(transcript: TranscriptResult) -> str:
    return "\n".join(segment.text.strip() for segment in transcript.segments)
