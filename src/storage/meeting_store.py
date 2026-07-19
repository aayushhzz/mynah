from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import date
from pathlib import Path

from common.types import Meeting
from storage.id_generator import reserve_meeting_folder

_METADATA_FILENAME = "metadata.json"
_TRANSCRIPT_FILENAME = "transcript.md"
_SUMMARY_FILENAME = "summary.md"
_ACTIONS_FILENAME = "actions.md"


class SourceFileNotFoundError(Exception):
    pass


def _meeting_to_json(meeting: Meeting) -> str:
    data = asdict(meeting)
    data["date"] = meeting.date.isoformat()
    data["folder"] = str(meeting.folder)
    return json.dumps(data, indent=2)


def _meeting_from_json(raw: str) -> Meeting:
    data = json.loads(raw)
    data["date"] = date.fromisoformat(data["date"])
    data["folder"] = Path(data["folder"])
    return Meeting(**data)


def load_meeting_metadata(metadata_path: Path) -> Meeting:
    return _meeting_from_json(Path(metadata_path).read_text())


class MeetingHandle:
    def __init__(self, folder: Path):
        self.folder = folder

    def save_audio(self, source_path: Path) -> Path:
        source_path = Path(source_path)
        if not source_path.exists():
            raise SourceFileNotFoundError(f"Audio source not found: {source_path}")
        dest_path = self.folder / source_path.name
        shutil.move(str(source_path), str(dest_path))
        return dest_path

    def save_transcript(self, markdown: str) -> Path:
        return self._save_text(_TRANSCRIPT_FILENAME, markdown)

    def save_summary(self, markdown: str) -> Path:
        return self._save_text(_SUMMARY_FILENAME, markdown)

    def save_actions(self, markdown: str) -> Path:
        return self._save_text(_ACTIONS_FILENAME, markdown)

    def save_metadata(self, meeting: Meeting) -> Path:
        return self._save_text(_METADATA_FILENAME, _meeting_to_json(meeting))

    def load_metadata(self) -> Meeting:
        path = self.folder / _METADATA_FILENAME
        return _meeting_from_json(path.read_text())

    def _save_text(self, filename: str, content: str) -> Path:
        path = self.folder / filename
        path.write_text(content)
        return path


class MeetingStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def create_meeting(self, when: date | None = None) -> MeetingHandle:
        folder = reserve_meeting_folder(self.base_dir, when)
        return MeetingHandle(folder)
