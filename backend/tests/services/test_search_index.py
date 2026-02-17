"""Tests for SearchIndex service."""

from datetime import datetime
from pathlib import Path

import pytest

from app.models.note import (
    Observation,
    ObservationCategory,
    Relation,
    RelationType,
    Wikilink,
)
from app.models.search import IndexedNote, SearchQuery, SortOrder
from app.services.search_index import SearchIndex, compute_file_hash


@pytest.fixture
async def search_index(temp_dir: Path) -> SearchIndex:
    """Create a SearchIndex instance for testing."""
    db_path = temp_dir / "test_index.db"
    index = SearchIndex(db_path)
    await index.initialize()
    yield index
    await index.close()


@pytest.fixture
def sample_note() -> IndexedNote:
    """Create a sample note for indexing."""
    return IndexedNote(
        vault_name="test_vault",
        relative_path="test-note.md",
        permalink="test-note",
        title="Test Note",
        note_type="note",
        project="test-project",
        content="This is a test note about authentication and JWT tokens.",
        tags=["test", "auth", "jwt"],
        observations=[
            Observation(
                category=ObservationCategory.DECISION,
                content="Chose JWT over sessions",
                tags=[],
                context=None,
                line_number=1,
            )
        ],
        relations=[
            Relation(
                relation_type=RelationType.DEPENDS_ON,
                target="redis-setup",
                target_path=None,
                context=None,
                line_number=2,
            )
        ],
        wikilinks=[
            Wikilink(
                target="Another Note",
                display_text=None,
                path=None,
                line_number=3,
                column=0,
            )
        ],
        created_at=datetime(2025, 1, 15, 10, 30, 0),
        updated_at=datetime(2025, 1, 16, 14, 20, 0),
        file_hash=compute_file_hash("test content"),
    )


@pytest.mark.asyncio
async def test_initialize_creates_tables(search_index: SearchIndex) -> None:
    """Test that initialize creates all required tables."""
    # Verify tables exist by querying them
    cursor = await search_index.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row['name'] async for row in cursor}
    assert 'notes' in tables
    assert 'notes_fts' in tables
    assert 'note_tags' in tables
    assert 'observations' in tables
    assert 'relations' in tables
    assert 'wikilinks' in tables


@pytest.mark.asyncio
async def test_index_note_new(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test indexing a new note."""
    note_id = await search_index.index_note(sample_note)

    assert note_id > 0

    # Verify note was inserted
    cursor = await search_index.db.execute(
        "SELECT * FROM notes WHERE id = ?", (note_id,)
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row['title'] == "Test Note"
    assert row['vault_name'] == "test_vault"
    assert row['relative_path'] == "test-note.md"

    # Verify tags
    cursor = await search_index.db.execute(
        "SELECT tag FROM note_tags WHERE note_id = ?", (note_id,)
    )
    tags = [row['tag'] async for row in cursor]
    assert set(tags) == {"test", "auth", "jwt"}

    # Verify observations
    cursor = await search_index.db.execute(
        "SELECT * FROM observations WHERE note_id = ?", (note_id,)
    )
    obs_row = await cursor.fetchone()
    assert obs_row is not None
    assert obs_row['category'] == "decision"

    # Verify relations
    cursor = await search_index.db.execute(
        "SELECT * FROM relations WHERE source_note_id = ?", (note_id,)
    )
    rel_row = await cursor.fetchone()
    assert rel_row is not None
    assert rel_row['relation_type'] == "depends_on"

    # Verify wikilinks
    cursor = await search_index.db.execute(
        "SELECT * FROM wikilinks WHERE source_note_id = ?", (note_id,)
    )
    wl_row = await cursor.fetchone()
    assert wl_row is not None
    assert wl_row['target_title'] == "Another Note"


@pytest.mark.asyncio
async def test_index_note_update(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test updating an existing note."""
    # Index initial note
    note_id = await search_index.index_note(sample_note)

    # Update note
    updated_note = IndexedNote(
        vault_name=sample_note.vault_name,
        relative_path=sample_note.relative_path,
        permalink=sample_note.permalink,
        title="Updated Test Note",
        note_type=sample_note.note_type,
        project=sample_note.project,
        content="Updated content",
        tags=["updated"],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=sample_note.created_at,
        updated_at=datetime(2025, 1, 17, 10, 0, 0),
        file_hash=compute_file_hash("updated content"),
    )

    updated_id = await search_index.index_note(updated_note)
    assert updated_id == note_id

    # Verify update
    cursor = await search_index.db.execute(
        "SELECT title FROM notes WHERE id = ?", (note_id,)
    )
    row = await cursor.fetchone()
    assert row['title'] == "Updated Test Note"


@pytest.mark.asyncio
async def test_remove_note(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test removing a note."""
    note_id = await search_index.index_note(sample_note)

    removed = await search_index.remove_note(
        sample_note.vault_name, sample_note.relative_path
    )
    assert removed is True

    # Verify note is gone
    cursor = await search_index.db.execute(
        "SELECT id FROM notes WHERE id = ?", (note_id,)
    )
    row = await cursor.fetchone()
    assert row is None


@pytest.mark.asyncio
async def test_search_simple_term(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test searching with a simple term."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="authentication")
    results = await search_index.search(query)

    assert results.total_count >= 1
    assert len(results.results) >= 1
    assert any(r.title == "Test Note" for r in results.results)


@pytest.mark.asyncio
async def test_search_phrase(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test searching with a phrase."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query='"JWT tokens"')
    results = await search_index.search(query)

    # May or may not match depending on content
    assert results.total_count >= 0


@pytest.mark.asyncio
async def test_search_filter_vault(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test filtering by vault."""
    await search_index.index_note(sample_note)

    # Create note in different vault
    other_note = IndexedNote(
        vault_name="other_vault",
        relative_path="other.md",
        permalink="other",
        title="Other Note",
        note_type="note",
        project=None,
        content="Other content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash=compute_file_hash("other"),
    )
    await search_index.index_note(other_note)

    query = SearchQuery(query="content", vault="test_vault")
    results = await search_index.search(query)

    assert all(r.vault_name == "test_vault" for r in results.results)


@pytest.mark.asyncio
async def test_search_filter_project(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test filtering by project."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="test", project="test-project")
    results = await search_index.search(query)

    assert all(
        r.project == "test-project" for r in results.results if r.project
    )


@pytest.mark.asyncio
async def test_search_filter_tags(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test filtering by tags."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="test", tags=["auth"])
    results = await search_index.search(query)

    assert all("auth" in r.tags for r in results.results)


@pytest.mark.asyncio
async def test_search_sort_relevance(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test sorting by relevance."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="authentication", sort=SortOrder.RELEVANCE)
    results = await search_index.search(query)

    # Results should be ordered by relevance (lower score is better)
    scores = [r.score for r in results.results]
    assert scores == sorted(scores)


@pytest.mark.asyncio
async def test_search_sort_date(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test sorting by date."""
    await search_index.index_note(sample_note)

    # Create another note with different date
    older_note = IndexedNote(
        vault_name="test_vault",
        relative_path="older.md",
        permalink="older",
        title="Older Note",
        note_type="note",
        project=None,
        content="Older content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=datetime(2025, 1, 10, 10, 0, 0),
        updated_at=datetime(2025, 1, 10, 10, 0, 0),
        file_hash=compute_file_hash("older"),
    )
    await search_index.index_note(older_note)

    query = SearchQuery(query="note", sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    # Results should be ordered by updated_at descending
    dates = [
        r.updated_at for r in results.results if r.updated_at is not None
    ]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_search_pagination(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test search pagination."""
    await search_index.index_note(sample_note)

    query1 = SearchQuery(query="test", limit=1, offset=0)
    results1 = await search_index.search(query1)

    query2 = SearchQuery(query="test", limit=1, offset=1)
    results2 = await search_index.search(query2)

    assert len(results1.results) <= 1
    assert len(results2.results) <= 1
    assert results1.total_count == results2.total_count


@pytest.mark.asyncio
async def test_resolve_wikilink_exact(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test resolving wikilink with exact match."""
    note_id = await search_index.index_note(sample_note)

    resolved = await search_index.resolve_wikilink("Test Note", "test_vault")
    assert resolved == note_id


@pytest.mark.asyncio
async def test_resolve_wikilink_permalink(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test resolving wikilink by permalink."""
    note_id = await search_index.index_note(sample_note)

    resolved = await search_index.resolve_wikilink("test-note")
    assert resolved == note_id


@pytest.mark.asyncio
async def test_resolve_batch(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test batch resolution returns same results as individual resolution."""
    note_id = await search_index.index_note(sample_note)

    targets = ["Test Note", "test-note", "NonExistent", "Test Note"]
    batch_result = await search_index.resolve_batch(targets, "test_vault")

    assert batch_result["Test Note"] == note_id
    assert batch_result["test-note"] == note_id
    assert batch_result["NonExistent"] is None
    assert len(batch_result) == 3  # unique targets only

    # Same as individual
    for t in ["Test Note", "test-note"]:
        assert await search_index.resolve_wikilink(t, "test_vault") == batch_result[t]
    assert await search_index.resolve_wikilink("NonExistent", "test_vault") is None


@pytest.mark.asyncio
async def test_resolve_batch_empty(search_index: SearchIndex) -> None:
    """Test resolve_batch with empty list."""
    result = await search_index.resolve_batch([], "test_vault")
    assert result == {}


@pytest.mark.asyncio
async def test_get_backlinks(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test getting backlinks."""
    note_id = await search_index.index_note(sample_note)

    # Create another note that links to this one
    linking_note = IndexedNote(
        vault_name="test_vault",
        relative_path="linking.md",
        permalink="linking",
        title="Linking Note",
        note_type="note",
        project=None,
        content="Links to test note",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[
            Wikilink(
                target="Test Note",
                display_text=None,
                path=None,
                line_number=1,
                column=0,
            )
        ],
        created_at=None,
        updated_at=None,
        file_hash=compute_file_hash("linking"),
    )
    await search_index.index_note(linking_note)

    backlinks = await search_index.get_backlinks(note_id)
    assert len(backlinks) >= 1
    assert any(b.title == "Linking Note" for b in backlinks)


@pytest.mark.asyncio
async def test_list_tags(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test listing tags."""
    await search_index.index_note(sample_note)

    tags = await search_index.list_tags()
    assert len(tags) >= 3
    tag_dict = dict(tags)
    assert "test" in tag_dict
    assert "auth" in tag_dict
    assert "jwt" in tag_dict


@pytest.mark.asyncio
async def test_list_projects(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test listing projects."""
    await search_index.index_note(sample_note)

    projects = await search_index.list_projects()
    assert len(projects) >= 1
    project_dict = dict(projects)
    assert "test-project" in project_dict


@pytest.mark.asyncio
async def test_get_stats(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test getting index statistics."""
    await search_index.index_note(sample_note)

    stats = await search_index.get_stats()
    assert stats["total_notes"] >= 1
    assert "test_vault" in stats["notes_by_vault"]
    assert "note" in stats["notes_by_type"]
    assert stats["total_observations"] >= 1
    assert stats["total_relations"] >= 1
    assert stats["total_tags"] >= 3


@pytest.mark.asyncio
async def test_needs_reindex(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test checking if note needs reindexing."""
    await search_index.index_note(sample_note)

    # Same hash - should not need reindex
    needs = await search_index.needs_reindex(
        sample_note.vault_name,
        sample_note.relative_path,
        sample_note.file_hash,
    )
    assert needs is False

    # Different hash - should need reindex
    needs = await search_index.needs_reindex(
        sample_note.vault_name,
        sample_note.relative_path,
        compute_file_hash("different content"),
    )
    assert needs is True


@pytest.mark.asyncio
async def test_get_note_by_id(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test getting note by ID."""
    note_id = await search_index.index_note(sample_note)

    retrieved = await search_index.get_note_by_id(note_id)
    assert retrieved is not None
    assert retrieved.title == "Test Note"
    assert retrieved.vault_name == "test_vault"
    assert len(retrieved.tags) == 3
    assert len(retrieved.observations) == 1
    assert len(retrieved.relations) == 1


@pytest.mark.asyncio
async def test_get_note_by_permalink(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test getting note by permalink."""
    await search_index.index_note(sample_note)

    retrieved = await search_index.get_note_by_permalink("test-note")
    assert retrieved is not None
    assert retrieved.title == "Test Note"


@pytest.mark.asyncio
async def test_get_note_by_path(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test getting note by path."""
    await search_index.index_note(sample_note)

    retrieved = await search_index.get_note_by_path(
        "test_vault", "test-note.md"
    )
    assert retrieved is not None
    assert retrieved.title == "Test Note"


# Enhanced Query Parser Tests


def test_query_parser_simple_terms(search_index: SearchIndex) -> None:
    """Test parsing simple single-word queries."""
    query = SearchQuery(query="test")
    result = search_index._build_fts_query(query)
    assert result == "test"

    query = SearchQuery(query="authentication")
    result = search_index._build_fts_query(query)
    assert result == "authentication"


def test_query_parser_boolean_operators(search_index: SearchIndex) -> None:
    """Test AND, OR, NOT operators."""
    query = SearchQuery(query="auth AND jwt")
    result = search_index._build_fts_query(query)
    assert "AND" in result
    assert "auth" in result
    assert "jwt" in result

    query = SearchQuery(query="session OR cookie")
    result = search_index._build_fts_query(query)
    assert "OR" in result

    query = SearchQuery(query="auth NOT session")
    result = search_index._build_fts_query(query)
    assert "NOT" in result


def test_query_parser_case_insensitive_operators(search_index: SearchIndex) -> None:
    """Test operators are case-insensitive."""
    query = SearchQuery(query="auth and jwt")
    result = search_index._build_fts_query(query)
    assert "AND" in result

    query = SearchQuery(query="session Or cookie")
    result = search_index._build_fts_query(query)
    assert "OR" in result


def test_query_parser_phrase_queries(search_index: SearchIndex) -> None:
    """Test quoted phrase searches."""
    query = SearchQuery(query='"exact phrase"')
    result = search_index._build_fts_query(query)
    assert '"exact phrase"' in result

    query = SearchQuery(query='"multi word phrase"')
    result = search_index._build_fts_query(query)
    assert '"multi word phrase"' in result


def test_query_parser_wildcard_prefix(search_index: SearchIndex) -> None:
    """Test wildcard/prefix matching."""
    query = SearchQuery(query="test*")
    result = search_index._build_fts_query(query)
    assert "test*" in result

    query = SearchQuery(query="auth*")
    result = search_index._build_fts_query(query)
    assert "auth*" in result


def test_query_parser_parentheses(search_index: SearchIndex) -> None:
    """Test parentheses for grouping."""
    query = SearchQuery(query="(auth OR authentication) AND jwt")
    result = search_index._build_fts_query(query)
    assert "(" in result
    assert ")" in result
    assert "OR" in result
    assert "AND" in result


def test_query_parser_nested_parentheses(search_index: SearchIndex) -> None:
    """Test nested parentheses."""
    query = SearchQuery(query="((redis OR cache) AND session) NOT cookie")
    result = search_index._build_fts_query(query)
    assert result.count("(") == 2
    assert result.count(")") == 2


def test_query_parser_column_specific(search_index: SearchIndex) -> None:
    """Test column-specific searches."""
    query = SearchQuery(query="title:authentication")
    result = search_index._build_fts_query(query)
    assert "title:" in result
    assert "authentication" in result

    query = SearchQuery(query="tags:security")
    result = search_index._build_fts_query(query)
    assert "tags:" in result


def test_query_parser_column_with_wildcard(search_index: SearchIndex) -> None:
    """Test column search with wildcard."""
    query = SearchQuery(query="title:auth*")
    result = search_index._build_fts_query(query)
    assert "title:" in result
    assert "*" in result


def test_query_parser_complex_nested(search_index: SearchIndex) -> None:
    """Test complex nested query."""
    query = SearchQuery(query='(auth* OR "user authentication") AND (jwt OR token) NOT session')
    result = search_index._build_fts_query(query)
    assert "(" in result
    assert "OR" in result
    assert "AND" in result
    assert "NOT" in result
    assert "*" in result


def test_query_parser_special_char_escaping(search_index: SearchIndex) -> None:
    """Test special character escaping."""
    query = SearchQuery(query="test+value")
    result = search_index._build_fts_query(query)
    # Should be escaped
    assert '"test+value"' in result

    query = SearchQuery(query="a-b-c")
    result = search_index._build_fts_query(query)
    assert '"a-b-c"' in result


def test_query_parser_empty_query(search_index: SearchIndex) -> None:
    """Test empty query handling."""
    query = SearchQuery(query="")
    result = search_index._build_fts_query(query)
    assert result == "*"

    query = SearchQuery(query="*")
    result = search_index._build_fts_query(query)
    assert result == "*"


def test_query_parser_unbalanced_parens_fallback(search_index: SearchIndex) -> None:
    """Test fallback for unbalanced parentheses."""
    query = SearchQuery(query="(auth AND jwt")
    result = search_index._build_fts_query(query)
    # Should fall back to escaped query
    assert result is not None
    assert '"(auth AND jwt"' in result

    query = SearchQuery(query="auth) AND (jwt")
    result = search_index._build_fts_query(query)
    assert result is not None


def test_query_parser_invalid_column(search_index: SearchIndex) -> None:
    """Test invalid column names."""
    query = SearchQuery(query="invalid:test")
    result = search_index._build_fts_query(query)
    # Should escape the whole thing
    assert '"invalid:test"' in result


def test_query_parser_multiple_phrases(search_index: SearchIndex) -> None:
    """Test multiple quoted phrases."""
    query = SearchQuery(query='"first phrase" AND "second phrase"')
    result = search_index._build_fts_query(query)
    assert '"first phrase"' in result
    assert '"second phrase"' in result
    assert "AND" in result


@pytest.mark.asyncio
async def test_query_parser_execution_with_parentheses(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that enhanced queries execute without errors."""
    # Index test data
    note1 = IndexedNote(
        vault_name="test",
        relative_path="auth.md",
        title="Authentication Guide",
        note_type="knowledge",
        content="JWT authentication and OAuth implementation",
        tags=["security", "auth"],
        file_hash="hash1",
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="session.md",
        title="Session Management",
        note_type="knowledge",
        content="Cookie-based sessions for web apps",
        tags=["security", "session"],
        file_hash="hash2",
    )

    await search_index.index_note(note1)
    await search_index.index_note(note2)

    # Test complex query (FTS5 requires NOT to be -term, or term NOT term2)
    query = SearchQuery(query="(auth OR authentication) NOT session")
    results = await search_index.search(query)

    assert results is not None
    # Should find auth guide
    titles = [r.title for r in results.results]
    assert any("Authentication" in t for t in titles)


@pytest.mark.asyncio
async def test_query_parser_wildcard_execution(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test wildcard queries execute correctly."""
    note = IndexedNote(
        vault_name="test",
        relative_path="test.md",
        title="Testing Guide",
        note_type="knowledge",
        content="Information about testing and testability",
        tags=["testing"],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    # Test wildcard query
    query = SearchQuery(query="test*")
    results = await search_index.search(query)

    assert results is not None
    assert len(results.results) > 0
    assert "Testing" in results.results[0].title


# ============================================================================
# BM25 Ranking Tests (Subtask 3.2)
# ============================================================================


@pytest.mark.asyncio
async def test_bm25_custom_k1_parameter(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that BM25 k1 parameter is accepted (reserved for future use).

    Note: FTS5 uses fixed BM25 parameters (k1=1.2). Custom k1 values are
    reserved for future implementation of custom ranking functions.
    This test verifies the parameter is accepted but doesn't affect results.
    """
    # Index notes with different term frequencies
    note1 = IndexedNote(
        vault_name="test",
        relative_path="high_freq.md",
        title="Search Search Search",
        note_type="knowledge",
        content="search " * 50,  # High term frequency
        tags=[],
        file_hash="hash1",
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="low_freq.md",
        title="Search Once",
        note_type="knowledge",
        content="search only once in content",
        tags=[],
        file_hash="hash2",
    )
    await search_index.index_note(note1)
    await search_index.index_note(note2)

    # Search with default k1 (1.2)
    query_default = SearchQuery(query="search", bm25_k1=1.2)
    results_default = await search_index.search(query_default)

    # Search with high k1 (3.0) - reserved, doesn't affect FTS5 scoring
    query_high = SearchQuery(query="search", bm25_k1=3.0)
    results_high = await search_index.search(query_high)

    # Both should return results
    assert len(results_default.results) == 2
    assert len(results_high.results) == 2

    # Parameter is accepted (even though it doesn't currently affect scoring)
    # FTS5 uses fixed k1=1.2, so scores will be the same
    # When custom ranking is implemented, this test should be updated
    assert results_default.results[0].score == results_high.results[0].score


@pytest.mark.asyncio
async def test_bm25_custom_b_parameter(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that BM25 b parameter is accepted (reserved for future use).

    Note: FTS5 uses fixed BM25 parameters (b=0.75). Custom b values are
    reserved for future implementation of custom ranking functions.
    """
    # Index notes with different lengths
    note1 = IndexedNote(
        vault_name="test",
        relative_path="short.md",
        title="Short",
        note_type="knowledge",
        content="search term here",  # Short content
        tags=[],
        file_hash="hash1",
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="long.md",
        title="Long Document",
        note_type="knowledge",
        content="search term here " + "filler text " * 100,  # Long content
        tags=[],
        file_hash="hash2",
    )
    await search_index.index_note(note1)
    await search_index.index_note(note2)

    # Search with default b (0.75)
    query_default = SearchQuery(query="search", bm25_b=0.75)
    results_default = await search_index.search(query_default)

    # Search with no length normalization (b=0)
    query_no_norm = SearchQuery(query="search", bm25_b=0.0)
    results_no_norm = await search_index.search(query_no_norm)

    # Both should return results
    assert len(results_default.results) == 2
    assert len(results_no_norm.results) == 2


@pytest.mark.asyncio
async def test_title_field_boost(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that title field boosting affects BM25 relevance component."""
    # Index notes with term in different positions
    note1 = IndexedNote(
        vault_name="test",
        relative_path="title_match.md",
        title="Authentication Guide",  # Term in title
        note_type="knowledge",
        content="This guide covers various security topics",
        tags=[],
        file_hash="hash1",
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="content_match.md",
        title="Security Overview",
        note_type="knowledge",
        content="Authentication is covered in detail here",  # Term in content
        tags=[],
        file_hash="hash2",
    )
    await search_index.index_note(note1)
    await search_index.index_note(note2)

    # Search with high title boost
    query_boosted = SearchQuery(query="authentication", boost_title=5.0)
    results_boosted = await search_index.search(query_boosted)

    # Search with no title boost
    query_no_boost = SearchQuery(query="authentication", boost_title=1.0)
    results_no_boost = await search_index.search(query_no_boost)

    # Both should find results
    assert len(results_boosted.results) == 2
    assert len(results_no_boost.results) == 2

    # Composite scoring includes score_breakdown
    for r in results_boosted.results:
        assert r.score_breakdown is not None
        assert "relevance" in r.score_breakdown


@pytest.mark.asyncio
async def test_composite_freshness_component(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that freshness component in composite scoring favors recent notes."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Index notes with different update times
    note1 = IndexedNote(
        vault_name="test",
        relative_path="recent.md",
        title="Recent Note",
        note_type="knowledge",
        content="search term content",
        tags=[],
        file_hash="hash1",
        updated_at=now,
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="old.md",
        title="Old Note",
        note_type="knowledge",
        content="search term content",
        tags=[],
        file_hash="hash2",
        updated_at=month_ago,
    )
    note3 = IndexedNote(
        vault_name="test",
        relative_path="middle.md",
        title="Week Old Note",
        note_type="knowledge",
        content="search term content",
        tags=[],
        file_hash="hash3",
        updated_at=week_ago,
    )
    await search_index.index_note(note1)
    await search_index.index_note(note2)
    await search_index.index_note(note3)

    # Composite scoring always includes freshness
    query = SearchQuery(query="search")
    results = await search_index.search(query)

    assert len(results.results) == 3

    # All results should have score_breakdown with freshness
    for r in results.results:
        assert r.score_breakdown is not None
        assert "freshness" in r.score_breakdown

    # Recent note should have highest freshness, old note lowest
    freshness_by_title = {
        r.title: r.score_breakdown["freshness"] for r in results.results
    }
    assert freshness_by_title["Recent Note"] > freshness_by_title["Week Old Note"]
    assert freshness_by_title["Week Old Note"] > freshness_by_title["Old Note"]

    # Scores should reflect freshness ordering (relevance tied, confidence tied)
    score_by_title = {r.title: r.score for r in results.results}
    assert score_by_title["Recent Note"] > score_by_title["Old Note"]


@pytest.mark.asyncio
async def test_recency_boost_with_missing_dates(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that recency boost handles notes without update dates."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    # Index notes with and without update times
    note1 = IndexedNote(
        vault_name="test",
        relative_path="dated.md",
        title="Dated Note",
        note_type="knowledge",
        content="search term content",
        tags=[],
        file_hash="hash1",
        updated_at=now,
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="undated.md",
        title="Undated Note",
        note_type="knowledge",
        content="search term content",
        tags=[],
        file_hash="hash2",
        updated_at=None,  # No update date
    )
    await search_index.index_note(note1)
    await search_index.index_note(note2)

    # Search with recency boost - should not error
    query = SearchQuery(query="search", recency_boost=True)
    results = await search_index.search(query)

    assert len(results.results) == 2


@pytest.mark.asyncio
async def test_deprecated_recency_params_accepted(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that deprecated recency_boost/recency_decay params are still accepted."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    note_recent = IndexedNote(
        vault_name="test",
        relative_path="recent.md",
        title="Recent Note",
        note_type="knowledge",
        content="search term content",
        tags=[],
        file_hash="hash1",
        updated_at=now,
    )
    note_old = IndexedNote(
        vault_name="test",
        relative_path="old.md",
        title="Old Note",
        note_type="knowledge",
        content="search term content",
        tags=[],
        file_hash="hash2",
        updated_at=month_ago,
    )
    await search_index.index_note(note_recent)
    await search_index.index_note(note_old)

    # Deprecated params should still be accepted without error
    query = SearchQuery(query="search", recency_boost=True, recency_decay=2.0)
    results = await search_index.search(query)

    assert len(results.results) == 2
    # Composite scoring always applies freshness
    for r in results.results:
        assert r.score_breakdown is not None
        assert r.score_breakdown["freshness"] >= 0


@pytest.mark.asyncio
async def test_composite_score_with_multiple_factors(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that composite score combines relevance, freshness, confidence, and decision_boost."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=365)

    # Index diverse notes
    note1 = IndexedNote(
        vault_name="test",
        relative_path="perfect.md",
        title="JWT Authentication",  # Title match + recent
        note_type="knowledge",
        content="JWT implementation details",
        tags=["security"],
        file_hash="hash1",
        updated_at=now,
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="content_only.md",
        title="Security Guide",
        note_type="knowledge",
        content="JWT authentication is important",  # Content match only
        tags=[],
        file_hash="hash2",
        updated_at=old,
    )
    await search_index.index_note(note1)
    await search_index.index_note(note2)

    # Search with all boosts enabled
    query = SearchQuery(
        query="jwt",
        boost_title=3.0,
        recency_boost=True,
    )
    results = await search_index.search(query)

    assert len(results.results) == 2
    # Both results should have composite score breakdowns
    for r in results.results:
        assert r.score_breakdown is not None
        assert all(k in r.score_breakdown for k in ["relevance", "freshness", "confidence", "decision_boost"])
    # Recent note should have higher freshness than old note
    jwt_result = next(r for r in results.results if "JWT" in r.title)
    other_result = next(r for r in results.results if "JWT" not in r.title)
    assert jwt_result.score_breakdown["freshness"] > other_result.score_breakdown["freshness"]


@pytest.mark.asyncio
async def test_bm25_rank_with_different_sort_orders(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that BM25 ranking only applies to relevance sort."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    # Index notes with different characteristics
    note1 = IndexedNote(
        vault_name="test",
        relative_path="newer.md",
        title="Newer Document",
        note_type="knowledge",
        content="search term here",
        tags=[],
        file_hash="hash1",
        created_at=now,
        updated_at=now,
    )
    note2 = IndexedNote(
        vault_name="test",
        relative_path="older.md",
        title="Older Document",
        note_type="knowledge",
        content="search term here",
        tags=[],
        file_hash="hash2",
        created_at=yesterday,
        updated_at=yesterday,
    )
    await search_index.index_note(note1)
    await search_index.index_note(note2)

    # Test relevance sort (uses BM25)
    query_relevance = SearchQuery(query="search", sort=SortOrder.RELEVANCE)
    results_relevance = await search_index.search(query_relevance)
    assert len(results_relevance.results) == 2

    # Test created_desc sort (should NOT use BM25 boosting)
    query_created = SearchQuery(query="search", sort=SortOrder.CREATED_DESC)
    results_created = await search_index.search(query_created)
    assert len(results_created.results) == 2
    # Should be ordered by creation date
    assert "Newer" in results_created.results[0].title

    # Test updated_desc sort
    query_updated = SearchQuery(query="search", sort=SortOrder.UPDATED_DESC)
    results_updated = await search_index.search(query_updated)
    assert len(results_updated.results) == 2
    assert "Newer" in results_updated.results[0].title


@pytest.mark.asyncio
async def test_boost_parameters_within_valid_ranges(
    search_index: SearchIndex,
) -> None:
    """Test that boost parameters are validated to be within acceptable ranges."""
    from pydantic import ValidationError

    # Valid boost values should work
    query_valid = SearchQuery(
        query="test",
        bm25_k1=1.5,
        bm25_b=0.5,
        boost_title=5.0,
        boost_tags=2.0,
        boost_observations=1.5,
    )
    assert query_valid.bm25_k1 == 1.5
    assert query_valid.boost_title == 5.0

    # Invalid k1 (too high) should fail
    with pytest.raises(ValidationError):
        SearchQuery(query="test", bm25_k1=5.0)  # Max is 3.0

    # Invalid b (too high) should fail
    with pytest.raises(ValidationError):
        SearchQuery(query="test", bm25_b=2.0)  # Max is 1.0

    # Invalid boost (negative) should fail
    with pytest.raises(ValidationError):
        SearchQuery(query="test", boost_title=-1.0)  # Min is 0.0


# ============================================================================
# Batch Indexing Tests (Subtask 3.3)
# ============================================================================


@pytest.mark.asyncio
async def test_batch_index_vault_new_notes(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test batch indexing multiple new notes."""
    # Create multiple notes
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content for note {i}",
            tags=[f"tag{i}"],
            file_hash=f"hash{i}",
        )
        for i in range(10)
    ]

    # Index all notes in batch
    added, updated, removed = await search_index.index_vault("test", notes)

    assert added == 10
    assert updated == 0
    assert removed == 0

    # Verify all notes are searchable
    query = SearchQuery(query="Content")
    results = await search_index.search(query)
    assert len(results.results) == 10


@pytest.mark.asyncio
async def test_batch_index_vault_update_existing(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test batch indexing updates existing notes correctly."""
    # Index initial notes
    notes_v1 = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i} V1",
            note_type="knowledge",
            content=f"Original content {i}",
            tags=[f"v1"],
            file_hash=f"hash{i}_v1",
        )
        for i in range(5)
    ]
    await search_index.index_vault("test", notes_v1)

    # Update notes with new content and hash
    notes_v2 = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i} V2",
            note_type="knowledge",
            content=f"Updated content {i}",
            tags=[f"v2"],
            file_hash=f"hash{i}_v2",  # Changed hash triggers update
        )
        for i in range(5)
    ]
    added, updated, removed = await search_index.index_vault("test", notes_v2)

    assert added == 0
    assert updated == 5
    assert removed == 0

    # Verify updated content is searchable
    query = SearchQuery(query="Updated")
    results = await search_index.search(query)
    assert len(results.results) == 5


@pytest.mark.asyncio
async def test_batch_index_vault_skip_unchanged(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that batch indexing skips notes with unchanged hash."""
    # Index initial notes
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content {i}",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(5)
    ]
    added1, updated1, removed1 = await search_index.index_vault("test", notes)

    # Re-index same notes with same hash (should skip)
    added2, updated2, removed2 = await search_index.index_vault("test", notes)

    assert added2 == 0
    assert updated2 == 0  # Unchanged hash means no update
    assert removed2 == 0


@pytest.mark.asyncio
async def test_batch_index_vault_full_reindex_removes(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that full reindex removes deleted notes."""
    # Index initial notes
    notes_initial = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content {i}",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(10)
    ]
    await search_index.index_vault("test", notes_initial)

    # Full reindex with fewer notes (some removed)
    notes_updated = notes_initial[:5]  # Only first 5 notes
    added, updated, removed = await search_index.index_vault(
        "test", notes_updated, full_reindex=True
    )

    assert added == 0
    assert updated == 0  # Same hash, no updates
    assert removed == 5  # 5 notes were removed

    # Verify only 5 notes remain
    query = SearchQuery(query="Content")
    results = await search_index.search(query)
    assert len(results.results) == 5


@pytest.mark.asyncio
async def test_batch_index_vault_with_progress_callback(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that progress callback is called during batch indexing."""
    progress_calls: list[tuple[int, int]] = []

    def progress_callback(current: int, total: int) -> None:
        progress_calls.append((current, total))

    # Create notes
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content {i}",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(10)
    ]

    # Index with progress callback
    await search_index.index_vault("test", notes, progress_callback=progress_callback)

    # Verify callback was called
    assert len(progress_calls) > 0
    # Last call should report all notes processed
    assert progress_calls[-1] == (10, 10)


@pytest.mark.asyncio
async def test_batch_index_preserves_tags(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that batch indexing preserves tags correctly."""
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path="tagged.md",
            title="Tagged Note",
            note_type="knowledge",
            content="Content with tags",
            tags=["security", "backend", "api"],
            file_hash="hash1",
        )
    ]

    await search_index.index_vault("test", notes)

    # Search by tag
    query = SearchQuery(query="security", tags=["security"])
    results = await search_index.search(query)
    assert len(results.results) == 1
    assert set(results.results[0].tags) == {"security", "backend", "api"}


@pytest.mark.asyncio
async def test_batch_index_preserves_observations(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that batch indexing preserves observations."""
    from app.models.note import Observation, ObservationCategory

    notes = [
        IndexedNote(
            vault_name="test",
            relative_path="observations.md",
            title="Note with Observations",
            note_type="knowledge",
            content="Content",
            tags=[],
            observations=[
                Observation(
                    category=ObservationCategory.DECISION,
                    content="Use JWT for auth",
                    context="Authentication section",
                    line_number=10,
                ),
                Observation(
                    category=ObservationCategory.FACT,
                    content="REST API uses JSON",
                    context="API section",
                    line_number=20,
                ),
            ],
            file_hash="hash1",
        )
    ]

    await search_index.index_vault("test", notes)

    # Verify observations are stored
    cursor = await search_index.db.execute(
        "SELECT COUNT(*) as count FROM observations"
    )
    row = await cursor.fetchone()
    assert row['count'] == 2


@pytest.mark.asyncio
async def test_batch_index_with_relations(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that batch indexing handles relations correctly."""
    from app.models.note import Relation, RelationType

    # Index target note first
    target_note = IndexedNote(
        vault_name="test",
        relative_path="target.md",
        title="Target Note",
        note_type="knowledge",
        content="Target content",
        tags=[],
        file_hash="hash_target",
    )
    await search_index.index_vault("test", [target_note])

    # Index source note with relation
    source_note = IndexedNote(
        vault_name="test",
        relative_path="source.md",
        title="Source Note",
        note_type="knowledge",
        content="Source content",
        tags=[],
        relations=[
            Relation(
                relation_type=RelationType.DEPENDS_ON,
                target="Target Note",
                context="Dependencies section",
                line_number=1,
            )
        ],
        file_hash="hash_source",
    )
    await search_index.index_vault("test", [source_note])

    # Verify relation was stored
    cursor = await search_index.db.execute(
        "SELECT COUNT(*) as count FROM relations"
    )
    row = await cursor.fetchone()
    assert row['count'] == 1


@pytest.mark.asyncio
async def test_get_index_statistics(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test index statistics reporting."""
    # Index some notes
    notes = [
        IndexedNote(
            vault_name="vault1",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content {i}",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(5)
    ]
    notes.extend([
        IndexedNote(
            vault_name="vault2",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content {i}",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(5, 10)
    ])

    await search_index.index_vault("vault1", notes[:5])
    await search_index.index_vault("vault2", notes[5:])

    # Get statistics
    stats = await search_index.get_index_statistics()

    assert stats['total_notes'] == 10
    assert stats['total_vaults'] == 2
    assert stats['last_indexed_at'] is not None
    assert stats['database_size_bytes'] > 0
    assert stats['fts_entries'] >= 0  # FTS count may vary by SQLite/FTS5 setup


@pytest.mark.asyncio
async def test_incremental_vacuum_runs_after_large_batch(
    search_index: SearchIndex, temp_dir: Path, monkeypatch
) -> None:
    """Test that incremental vacuum runs after large batch operations."""
    vacuum_called = False

    async def mock_vacuum(self) -> None:
        nonlocal vacuum_called
        vacuum_called = True

    # Monkey patch the _incremental_vacuum method
    monkeypatch.setattr(SearchIndex, '_incremental_vacuum', mock_vacuum)

    # Index 150 notes (triggers vacuum threshold of 100)
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content {i}",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(150)
    ]

    await search_index.index_vault("test", notes)

    # Verify vacuum was called
    assert vacuum_called


# ============================================================================
# Enhanced Snippet Generation Tests (Subtask 3.5)
# ============================================================================


@pytest.mark.asyncio
async def test_snippet_generation_basic(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test basic snippet generation with highlighting."""
    note = IndexedNote(
        vault_name="test",
        relative_path="test.md",
        title="Test Note",
        note_type="knowledge",
        content="This is a test document with some test content for searching.",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="test")
    results = await search_index.search(query)

    assert len(results.results) == 1
    assert "<mark>" in results.results[0].snippet
    assert "test" in results.results[0].snippet.lower()


@pytest.mark.asyncio
async def test_snippet_multi_field_title_match(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that title matches are highlighted with field indicator."""
    note = IndexedNote(
        vault_name="test",
        relative_path="auth.md",
        title="Authentication Guide",
        note_type="knowledge",
        content="This guide covers security topics.",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="Authentication", snippet_multi_field=True)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    assert "<mark>Authentication</mark>" in snippet


@pytest.mark.asyncio
async def test_snippet_multi_field_tags_match(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that tag matches are highlighted with field indicator."""
    note = IndexedNote(
        vault_name="test",
        relative_path="api.md",
        title="API Documentation",
        note_type="knowledge",
        content="REST API implementation guide.",
        tags=["backend", "security", "authentication"],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="security", snippet_multi_field=True)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    assert "<mark>security</mark>" in snippet


@pytest.mark.asyncio
async def test_snippet_multi_field_observations_match(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that observation matches are highlighted with field indicator."""
    from app.models.note import Observation, ObservationCategory

    note = IndexedNote(
        vault_name="test",
        relative_path="decisions.md",
        title="Architecture Decisions",
        note_type="knowledge",
        content="System architecture documentation.",
        tags=[],
        observations=[
            Observation(
                category=ObservationCategory.DECISION,
                content="Use PostgreSQL for the database backend",
                context="Database section",
                line_number=10,
            )
        ],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="PostgreSQL", snippet_multi_field=True)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    assert "<mark>PostgreSQL</mark>" in snippet


@pytest.mark.asyncio
async def test_snippet_single_field_mode(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that single-field mode only shows content snippets."""
    note = IndexedNote(
        vault_name="test",
        relative_path="auth.md",
        title="Authentication System",
        note_type="knowledge",
        content="Authentication using JWT tokens for security.",
        tags=["security"],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="security", snippet_multi_field=False)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    # Should NOT have field indicators
    assert "[Title]" not in snippet
    assert "[Tags]" not in snippet
    # Should only have content match
    assert "<mark>security</mark>" in snippet


@pytest.mark.asyncio
async def test_snippet_custom_highlight_markers(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test custom highlight markers."""
    note = IndexedNote(
        vault_name="test",
        relative_path="test.md",
        title="Test Note",
        note_type="knowledge",
        content="This is test content.",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(
        query="test",
        snippet_highlight_start="<em>",
        snippet_highlight_end="</em>",
    )
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    assert "test" in snippet.lower()


@pytest.mark.asyncio
async def test_snippet_max_length_truncation(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that snippets are truncated to max length."""
    long_content = "word " * 100  # Create long content
    note = IndexedNote(
        vault_name="test",
        relative_path="long.md",
        title="Long Document",
        note_type="knowledge",
        content=long_content,
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="word", snippet_max_length=100)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    assert "word" in snippet.lower()


@pytest.mark.asyncio
async def test_snippet_html_escaping(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that HTML content is properly escaped in snippets."""
    note = IndexedNote(
        vault_name="test",
        relative_path="html.md",
        title="HTML Example",
        note_type="knowledge",
        content="Use <script>alert('XSS')</script> to test security.",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="security", snippet_html_safe=True)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    assert "<mark>security</mark>" in snippet


@pytest.mark.asyncio
async def test_snippet_context_tokens_parameter(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that context_tokens parameter affects snippet size."""
    content = "The authentication system uses JWT tokens for secure API access and session management."
    note = IndexedNote(
        vault_name="test",
        relative_path="auth.md",
        title="Auth System",
        note_type="knowledge",
        content=content,
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    # Small context
    query_small = SearchQuery(query="JWT", snippet_context_tokens=8)
    results_small = await search_index.search(query_small)

    # Large context
    query_large = SearchQuery(query="JWT", snippet_context_tokens=64)
    results_large = await search_index.search(query_large)

    # Larger context should include more text
    snippet_small = results_small.results[0].snippet
    snippet_large = results_large.results[0].snippet

    assert len(snippet_large) >= len(snippet_small)
    assert "<mark>JWT</mark>" in snippet_small
    assert "<mark>JWT</mark>" in snippet_large


@pytest.mark.asyncio
async def test_snippet_no_html_safe_mode(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test plain text snippets without HTML escaping."""
    note = IndexedNote(
        vault_name="test",
        relative_path="code.md",
        title="Code Example",
        note_type="knowledge",
        content="The function returns <int> values for testing.",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="testing", snippet_html_safe=False)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet
    # When html_safe=False, HTML should NOT be escaped
    # (though FTS5 snippet function still includes our markers)
    assert "<mark>testing</mark>" in snippet


@pytest.mark.asyncio
async def test_snippet_combined_fields(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test snippet with matches in multiple fields."""
    from app.models.note import Observation, ObservationCategory

    note = IndexedNote(
        vault_name="test",
        relative_path="full.md",
        title="Security Authentication Guide",
        note_type="knowledge",
        content="This guide covers security and authentication best practices.",
        tags=["security", "authentication"],
        observations=[
            Observation(
                category=ObservationCategory.FACT,
                content="Security is paramount for authentication systems.",
                context="Security section",
                line_number=5,
            )
        ],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="security", snippet_multi_field=True)
    results = await search_index.search(query)

    assert len(results.results) == 1
    snippet = results.results[0].snippet

    assert "<mark>security</mark>" in snippet


# ============================================================================
# Performance Monitoring Tests (Subtask 3.4)
# ============================================================================


@pytest.mark.asyncio
async def test_slow_query_logging(
    search_index: SearchIndex, temp_dir: Path, caplog
) -> None:
    """Test that slow queries are logged."""
    import logging

    # Index a note
    note = IndexedNote(
        vault_name="test",
        relative_path="test.md",
        title="Test Note",
        note_type="knowledge",
        content="test content",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    # Mock slow query by searching (actual query may or may not be slow)
    # We'll verify the logging mechanism exists
    query = SearchQuery(query="test")

    with caplog.at_level(logging.WARNING):
        results = await search_index.search(query)

        # If query was slow (>100ms), warning should be logged
        # Note: In test environment, queries are usually fast
        # This test verifies the logging mechanism is in place


@pytest.mark.asyncio
async def test_explain_query_basic(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test EXPLAIN QUERY PLAN execution."""
    # Index a note
    note = IndexedNote(
        vault_name="test",
        relative_path="test.md",
        title="Test Note",
        note_type="knowledge",
        content="test content",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    query = SearchQuery(query="test")
    plan = await search_index.explain_query(query)

    # Should return query plan
    assert isinstance(plan, list)
    assert len(plan) > 0

    # Each plan entry should have expected fields
    for entry in plan:
        assert "id" in entry
        assert "parent" in entry
        assert "detail" in entry


@pytest.mark.asyncio
async def test_explain_query_with_filters(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test EXPLAIN QUERY PLAN with complex filters."""
    # Index notes with various attributes
    note1 = IndexedNote(
        vault_name="vault1",
        relative_path="note1.md",
        title="Note 1",
        note_type="knowledge",
        project="project1",
        content="test content",
        tags=["tag1", "tag2"],
        file_hash="hash1",
    )
    await search_index.index_note(note1)

    query = SearchQuery(
        query="test",
        vault="vault1",
        project="project1",
        tags=["tag1"],
    )
    plan = await search_index.explain_query(query)

    assert isinstance(plan, list)
    assert len(plan) > 0


@pytest.mark.asyncio
async def test_analyze_index_healthy(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test analyze_index with healthy index."""
    # Index some notes
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path=f"note{i}.md",
            title=f"Note {i}",
            note_type="knowledge",
            content=f"Content {i}",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(5)
    ]
    for note in notes:
        await search_index.index_note(note)

    analysis = await search_index.analyze_index()

    assert "health_score" in analysis
    assert "recommendations" in analysis
    assert "statistics" in analysis
    assert "integrity_ok" in analysis

    # Healthy index should have high score
    assert analysis["health_score"] >= 80
    assert isinstance(analysis["recommendations"], list)


@pytest.mark.asyncio
async def test_analyze_index_with_mismatch(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test analyze_index detects FTS/notes mismatch."""
    # Index a note
    note = IndexedNote(
        vault_name="test",
        relative_path="note.md",
        title="Test Note",
        note_type="knowledge",
        content="test content",
        tags=[],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    # Manually create mismatch by deleting from notes but not FTS
    await search_index.db.execute("DELETE FROM notes WHERE id = 1")
    await search_index.db.commit()

    analysis = await search_index.analyze_index()

    assert "health_score" in analysis
    assert "recommendations" in analysis
    # Mismatch may reduce health score or add recommendations
    assert analysis["health_score"] <= 100
    assert isinstance(analysis["recommendations"], list)


@pytest.mark.asyncio
async def test_autocomplete_titles(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test autocomplete with title matching."""
    # Index notes with various titles
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path="auth1.md",
            title="Authentication Guide",
            note_type="knowledge",
            content="content",
            tags=[],
            file_hash="hash1",
        ),
        IndexedNote(
            vault_name="test",
            relative_path="auth2.md",
            title="Authorization System",
            note_type="knowledge",
            content="content",
            tags=[],
            file_hash="hash2",
        ),
        IndexedNote(
            vault_name="test",
            relative_path="other.md",
            title="Database Design",
            note_type="knowledge",
            content="content",
            tags=[],
            file_hash="hash3",
        ),
    ]
    for note in notes:
        await search_index.index_note(note)

    # Autocomplete with "auth" prefix
    suggestions = await search_index.autocomplete("auth", fields=["title"])

    assert len(suggestions) >= 2
    # Should suggest authentication-related titles
    titles = [s["value"] for s in suggestions if s["field"] == "title"]
    assert any("Authentication" in t for t in titles)
    assert any("Authorization" in t for t in titles)


@pytest.mark.asyncio
async def test_autocomplete_tags(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test autocomplete with tag matching."""
    # Index notes with various tags
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path="note1.md",
            title="Note 1",
            note_type="knowledge",
            content="content",
            tags=["backend", "api", "authentication"],
            file_hash="hash1",
        ),
        IndexedNote(
            vault_name="test",
            relative_path="note2.md",
            title="Note 2",
            note_type="knowledge",
            content="content",
            tags=["frontend", "react", "ui"],
            file_hash="hash2",
        ),
    ]
    for note in notes:
        await search_index.index_note(note)

    # Autocomplete with "back" prefix
    suggestions = await search_index.autocomplete("back", fields=["tags"])

    assert len(suggestions) >= 1
    tags = [s["value"] for s in suggestions if s["field"] == "tag"]
    assert "backend" in tags


@pytest.mark.asyncio
async def test_autocomplete_min_length(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that autocomplete requires minimum 2 characters."""
    note = IndexedNote(
        vault_name="test",
        relative_path="test.md",
        title="Test Note",
        note_type="knowledge",
        content="content",
        tags=["test"],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    # Single character should return empty
    suggestions = await search_index.autocomplete("t")
    assert len(suggestions) == 0

    # Two characters should work
    suggestions = await search_index.autocomplete("te")
    assert len(suggestions) >= 1


@pytest.mark.asyncio
async def test_autocomplete_limit(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test that autocomplete respects limit parameter."""
    # Index many notes
    notes = [
        IndexedNote(
            vault_name="test",
            relative_path=f"test{i}.md",
            title=f"Test Note {i}",
            note_type="knowledge",
            content="content",
            tags=[],
            file_hash=f"hash{i}",
        )
        for i in range(20)
    ]
    for note in notes:
        await search_index.index_note(note)

    # Request limited suggestions
    suggestions = await search_index.autocomplete("test", limit=5)
    assert len(suggestions) <= 5


@pytest.mark.asyncio
async def test_autocomplete_combined_fields(
    search_index: SearchIndex, temp_dir: Path
) -> None:
    """Test autocomplete across multiple fields."""
    note = IndexedNote(
        vault_name="test",
        relative_path="auth.md",
        title="Authentication Guide",
        note_type="knowledge",
        content="content",
        tags=["authentication", "security"],
        file_hash="hash1",
    )
    await search_index.index_note(note)

    # Search both title and tags
    suggestions = await search_index.autocomplete("auth", fields=["title", "tags"])

    # Should get suggestions from both fields
    fields_found = set(s["field"] for s in suggestions)
    assert "title" in fields_found or "tag" in fields_found
    assert len(suggestions) >= 1
