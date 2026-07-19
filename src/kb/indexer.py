from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date
from pathlib import Path

from common.types import Meeting
from storage.meeting_store import load_meeting_metadata

logger = logging.getLogger(__name__)

_UPSERT_SQL = """
INSERT INTO meetings (id, title, date, duration_seconds, language, participants, topics, status, folder)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    title = excluded.title,
    date = excluded.date,
    duration_seconds = excluded.duration_seconds,
    language = excluded.language,
    participants = excluded.participants,
    topics = excluded.topics,
    status = excluded.status,
    folder = excluded.folder;
"""


def _row_to_meeting(row: sqlite3.Row) -> Meeting:
    return Meeting(
        id=row["id"],
        title=row["title"],
        date=date.fromisoformat(row["date"]),
        duration_seconds=row["duration_seconds"],
        language=row["language"],
        participants=json.loads(row["participants"]),
        topics=json.loads(row["topics"]),
        status=row["status"],
        folder=Path(row["folder"]),
    )


class MeetingIndexer:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def index_meeting(self, meeting: Meeting) -> None:
        self._connection.execute(
            _UPSERT_SQL,
            (
                meeting.id,
                meeting.title,
                meeting.date.isoformat(),
                meeting.duration_seconds,
                meeting.language,
                json.dumps(meeting.participants or []),
                json.dumps(meeting.topics or []),
                meeting.status,
                str(meeting.folder),
            ),
        )
        self._connection.commit()

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        row = self._connection.execute(
            "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()
        return _row_to_meeting(row) if row else None

    def list_meetings(self, status: str | None = None) -> list[Meeting]:
        if status is None:
            rows = self._connection.execute(
                "SELECT * FROM meetings ORDER BY date DESC"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM meetings WHERE status = ? ORDER BY date DESC", (status,)
            ).fetchall()
        return [_row_to_meeting(row) for row in rows]

    def reindex_all(self, meetings_root: str | Path) -> None:
        for metadata_path in Path(meetings_root).glob("*/*/meeting-*/metadata.json"):
            try:
                meeting = load_meeting_metadata(metadata_path)
            except (json.JSONDecodeError, OSError, KeyError, TypeError) as exc:
                logger.warning("Skipping unreadable metadata at %s: %s", metadata_path, exc)
                continue
            self.index_meeting(meeting)
