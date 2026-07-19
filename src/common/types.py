from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str = "Speaker 1"


@dataclass
class TranscriptResult:
    segments: list[Segment]
    language: str
    audio_path: Path
    duration_seconds: float


@dataclass
class ActionItem:
    description: str
    owner: str | None = None
    due: str | None = None


@dataclass
class SummaryResult:
    executive_summary: str
    decisions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class Meeting:
    id: str
    title: str
    date: date
    duration_seconds: float
    language: str
    participants: list[str]
    topics: list[str]
    status: str
    folder: Path


@dataclass
class SearchResult:
    meeting_id: str
    title: str
    snippet: str
    score: float
