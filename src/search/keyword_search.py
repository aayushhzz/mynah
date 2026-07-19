from __future__ import annotations

import sqlite3

from common.types import SearchResult

_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS meetings_fts USING fts5(
    meeting_id UNINDEXED,
    title,
    transcript_text,
    summary_text,
    topics,
    tokenize = "unicode61 remove_diacritics 2"
);
"""


def init_search_index(connection: sqlite3.Connection) -> None:
    connection.execute(_SCHEMA)
    connection.commit()


def _sanitize_query(query: str) -> str:
    tokens = query.split()
    escaped_tokens = ['"' + token.replace('"', '""') + '"' for token in tokens]
    return " OR ".join(escaped_tokens)


class SearchIndexer:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def index_content(
        self,
        meeting_id: str,
        title: str,
        transcript_text: str,
        summary_text: str,
        topics: str,
    ) -> None:
        self._connection.execute(
            "DELETE FROM meetings_fts WHERE meeting_id = ?", (meeting_id,)
        )
        self._connection.execute(
            "INSERT INTO meetings_fts (meeting_id, title, transcript_text, summary_text, topics) "
            "VALUES (?, ?, ?, ?, ?)",
            (meeting_id, title, transcript_text, summary_text, topics),
        )
        self._connection.commit()


class KeywordSearch:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        if not query.strip():
            return []

        sanitized = _sanitize_query(query)
        if not sanitized:
            return []

        rows = self._connection.execute(
            """
            SELECT
                meeting_id,
                title,
                snippet(meetings_fts, -1, '[', ']', '...', 10) AS snippet,
                bm25(meetings_fts) AS score
            FROM meetings_fts
            WHERE meetings_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (sanitized, limit),
        ).fetchall()

        return [
            SearchResult(meeting_id=row[0], title=row[1], snippet=row[2], score=row[3])
            for row in rows
        ]
