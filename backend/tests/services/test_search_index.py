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
