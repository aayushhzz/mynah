from __future__ import annotations

from kb.database import init_db
from search.keyword_search import KeywordSearch, SearchIndexer, init_search_index


def _setup():
    connection = init_db(":memory:")
    init_search_index(connection)
    return connection


def test_table_creation():
    connection = _setup()
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='meetings_fts'"
    ).fetchall()
    assert len(rows) == 1


def test_index_and_search_finds_matches():
    connection = _setup()
    indexer = SearchIndexer(connection)
    indexer.index_content(
        "meeting-001", "Sprint Planning", "we discussed the quarterly roadmap", "summary text", "roadmap"
    )
    search = KeywordSearch(connection)

    results = search.search("roadmap")

    assert len(results) == 1
    assert results[0].meeting_id == "meeting-001"


def test_no_match_returns_empty_list():
    connection = _setup()
    indexer = SearchIndexer(connection)
    indexer.index_content("meeting-001", "Sprint Planning", "transcript", "summary", "topics")
    search = KeywordSearch(connection)

    assert search.search("nonexistentterm12345") == []


def test_empty_query_returns_empty_list_without_touching_db():
    connection = _setup()
    search = KeywordSearch(connection)

    assert search.search("") == []
    assert search.search("   ") == []


def test_special_fts5_characters_in_query_do_not_raise():
    connection = _setup()
    indexer = SearchIndexer(connection)
    indexer.index_content("meeting-001", "Title", "some transcript text", "summary", "topics")
    search = KeywordSearch(connection)

    for query in ["-leading-dash", '"unbalanced quote', "AND OR NOT", "*wildcard", "(parens)"]:
        results = search.search(query)
        assert isinstance(results, list)


def test_reindexing_same_meeting_id_overwrites_not_duplicates():
    connection = _setup()
    indexer = SearchIndexer(connection)
    indexer.index_content("meeting-001", "Old Title", "old transcript", "old summary", "old")
    indexer.index_content("meeting-001", "New Title", "new transcript unique-term-xyz", "new summary", "new")

    search = KeywordSearch(connection)
    results = search.search("unique-term-xyz")

    assert len(results) == 1
    assert results[0].title == "New Title"

    old_results = search.search("old")
    assert old_results == []


def test_multi_meeting_search_returns_only_relevant_ones():
    connection = _setup()
    indexer = SearchIndexer(connection)
    indexer.index_content("meeting-001", "Alpha", "discussion about widgets", "summary", "widgets")
    indexer.index_content("meeting-002", "Beta", "discussion about gadgets", "summary", "gadgets")
    indexer.index_content("meeting-003", "Gamma", "discussion about widgets and gadgets", "summary", "both")

    search = KeywordSearch(connection)
    results = search.search("widgets")

    result_ids = {r.meeting_id for r in results}
    assert result_ids == {"meeting-001", "meeting-003"}


def test_snippet_contains_matched_term():
    connection = _setup()
    indexer = SearchIndexer(connection)
    indexer.index_content(
        "meeting-001", "Title", "the quick brown fox jumps over the lazy dog", "summary", "topics"
    )
    search = KeywordSearch(connection)

    results = search.search("fox")

    assert "fox" in results[0].snippet


def test_search_integration():
    connection = _setup()
    indexer = SearchIndexer(connection)
    indexer.index_content("meeting-001", "Kickoff", "we talked about zebras extensively", "summary1", "animals")
    indexer.index_content("meeting-002", "Retro", "we talked about giraffes", "summary2", "animals")
    indexer.index_content("meeting-003", "Standup", "no animals mentioned here", "summary3", "none")

    search = KeywordSearch(connection)

    results = search.search("zebras")
    assert len(results) == 1
    assert results[0].meeting_id == "meeting-001"
    assert "zebras" in results[0].snippet

    no_results = search.search("nonexistentcreature")
    assert no_results == []
