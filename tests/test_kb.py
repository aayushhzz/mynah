from __future__ import annotations

from datetime import date
from pathlib import Path

from common.types import Meeting
from kb.database import init_db
from kb.indexer import MeetingIndexer


def _make_meeting(
    id="meeting-001",
    title="Sprint Planning",
    when=date(2026, 7, 19),
    status="recorded",
    folder=Path("/tmp/meeting-001"),
    participants=None,
    topics=None,
) -> Meeting:
    return Meeting(
        id=id,
        title=title,
        date=when,
        duration_seconds=1800.0,
        language="en",
        participants=participants if participants is not None else ["Alice"],
        topics=topics if topics is not None else ["roadmap"],
        status=status,
        folder=folder,
    )


def test_schema_created():
    connection = init_db(":memory:")
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row[0] for row in rows}
    assert "meetings" in table_names


def test_index_and_get_round_trips():
    connection = init_db(":memory:")
    indexer = MeetingIndexer(connection)
    meeting = _make_meeting()

    indexer.index_meeting(meeting)
    loaded = indexer.get_meeting("meeting-001")

    assert loaded == meeting


def test_duplicate_id_upserts_single_row_latest_status():
    connection = init_db(":memory:")
    indexer = MeetingIndexer(connection)
    meeting = _make_meeting(status="recorded")
    indexer.index_meeting(meeting)

    updated = _make_meeting(status="summarized")
    indexer.index_meeting(updated)

    all_rows = connection.execute("SELECT * FROM meetings").fetchall()
    assert len(all_rows) == 1
    loaded = indexer.get_meeting("meeting-001")
    assert loaded.status == "summarized"


def test_empty_lists_stored_as_empty_json_array_not_null():
    connection = init_db(":memory:")
    indexer = MeetingIndexer(connection)
    meeting = _make_meeting(participants=[], topics=[])

    indexer.index_meeting(meeting)

    row = connection.execute(
        "SELECT participants, topics FROM meetings WHERE id = ?", ("meeting-001",)
    ).fetchone()
    assert row[0] == "[]"
    assert row[1] == "[]"
    assert row[0] is not None
    assert row[1] is not None


def test_list_ordering_and_status_filtering():
    connection = init_db(":memory:")
    indexer = MeetingIndexer(connection)
    indexer.index_meeting(_make_meeting(id="meeting-001", when=date(2026, 7, 1), status="recorded"))
    indexer.index_meeting(_make_meeting(id="meeting-002", when=date(2026, 7, 15), status="indexed"))
    indexer.index_meeting(_make_meeting(id="meeting-003", when=date(2026, 7, 10), status="indexed"))

    all_meetings = indexer.list_meetings()
    assert [m.id for m in all_meetings] == ["meeting-002", "meeting-003", "meeting-001"]

    indexed_only = indexer.list_meetings(status="indexed")
    assert [m.id for m in indexed_only] == ["meeting-002", "meeting-003"]


def test_reindex_all_skips_folder_missing_metadata(tmp_path):
    meeting_folder = tmp_path / "2026" / "07" / "meeting-001"
    meeting_folder.mkdir(parents=True)
    incomplete_folder = tmp_path / "2026" / "07" / "meeting-002"
    incomplete_folder.mkdir(parents=True)

    from storage.meeting_store import MeetingStore

    store = MeetingStore(tmp_path)
    handle = store.create_meeting(when=date(2026, 7, 19))
    handle.save_metadata(_make_meeting(id="meeting-003", folder=handle.folder))

    connection = init_db(":memory:")
    indexer = MeetingIndexer(connection)

    indexer.reindex_all(tmp_path)

    assert indexer.get_meeting("meeting-003") is not None
    assert indexer.list_meetings() == [indexer.get_meeting("meeting-003")]


def test_status_progression_updates_same_row_no_duplicates():
    connection = init_db(":memory:")
    indexer = MeetingIndexer(connection)

    for status in ["recorded", "transcribed", "summarized", "indexed"]:
        indexer.index_meeting(_make_meeting(status=status))

    all_rows = connection.execute("SELECT * FROM meetings").fetchall()
    assert len(all_rows) == 1
    assert indexer.get_meeting("meeting-001").status == "indexed"


def test_kb_integration():
    connection = init_db(":memory:")
    indexer = MeetingIndexer(connection)

    m1 = _make_meeting(id="meeting-001", when=date(2026, 7, 1), status="recorded")
    m2 = _make_meeting(id="meeting-002", when=date(2026, 7, 10), status="summarized")
    m3 = _make_meeting(id="meeting-003", when=date(2026, 7, 5), status="indexed")

    for m in (m1, m2, m3):
        indexer.index_meeting(m)

    listed = indexer.list_meetings()
    assert [m.id for m in listed] == ["meeting-002", "meeting-003", "meeting-001"]

    updated_m1 = _make_meeting(id="meeting-001", when=date(2026, 7, 1), status="indexed")
    indexer.index_meeting(updated_m1)

    all_rows = connection.execute("SELECT * FROM meetings").fetchall()
    assert len(all_rows) == 3
    assert indexer.get_meeting("meeting-001").status == "indexed"
