"""Tests for SearchIndex service."""

from datetime import datetime
from pathlib import Path

import pytest

from app.models.note import (
    NoteType,
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
    """Create a SearchIndex instance with temporary database."""
    db_path = temp_dir / "test_index.db"
    index = SearchIndex(db_path)
    await index.initialize()
    yield index
    await index.close()


@pytest.fixture
def sample_note() -> IndexedNote:
    """Create a sample note for indexing."""
    content = "# Test Note\n\nThis is a test note about authentication and JWT tokens."
    return IndexedNote(
        vault_name="test_vault",
        relative_path="test-note.md",
        permalink="test-note",
        title="Test Note",
        note_type=NoteType.NOTE.value,
        project="test-project",
        content=content,
        tags=["test", "authentication"],
        observations=[
            Observation(
                category=ObservationCategory.TIP,
                content="Always use JWT for auth",
                tags=["security"],
                line_number=1,
            )
        ],
        relations=[
            Relation(
                relation_type=RelationType.DEPENDS_ON,
                target="Prerequisite Note",
                line_number=1,
            )
        ],
        wikilinks=[
            Wikilink(target="Linked Note", line_number=1, column=0)
        ],
        created_at=datetime(2025, 1, 15, 10, 0, 0),
        updated_at=datetime(2025, 1, 16, 14, 0, 0),
        file_hash=compute_file_hash(content),
    )


@pytest.mark.asyncio
async def test_initialize_creates_tables(search_index: SearchIndex) -> None:
    """Test that initialize creates all required tables."""
    # Tables should already be created by fixture
    # Just verify we can query them
    conn = await search_index._get_connection()
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in await cursor.fetchall()}

    assert "notes" in tables
    assert "notes_fts" in tables
    assert "note_tags" in tables
    assert "observations" in tables
    assert "relations" in tables
    assert "wikilinks" in tables


@pytest.mark.asyncio
async def test_index_note_new(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test indexing a new note."""
    note_id = await search_index.index_note(sample_note)

    assert note_id > 0

    # Verify note was inserted
    note = await search_index.get_note_by_id(note_id)
    assert note is not None
    assert note.title == sample_note.title
    assert note.vault_name == sample_note.vault_name


@pytest.mark.asyncio
async def test_index_note_update(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test updating an existing note."""
    # Index initially
    note_id = await search_index.index_note(sample_note)

    # Update and reindex
    sample_note.title = "Updated Title"
    sample_note.content = "Updated content"
    sample_note.file_hash = compute_file_hash(sample_note.content)
    updated_id = await search_index.index_note(sample_note)

    assert updated_id == note_id

    # Verify update
    note = await search_index.get_note_by_id(note_id)
    assert note is not None
    assert note.title == "Updated Title"


@pytest.mark.asyncio
async def test_remove_note(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test removing a note."""
    note_id = await search_index.index_note(sample_note)

    removed = await search_index.remove_note(
        sample_note.vault_name, sample_note.relative_path
    )

    assert removed is True

    # Verify note is gone
    note = await search_index.get_note_by_id(note_id)
    assert note is None


@pytest.mark.asyncio
async def test_search_simple_term(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test searching with a simple term."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="authentication")
    results = await search_index.search(query)

    assert results.total_count >= 1
    assert any(r.note_id for r in results.results)


@pytest.mark.asyncio
async def test_search_phrase(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test searching with a phrase."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query='JWT tokens')
    results = await search_index.search(query)

    assert results.total_count >= 1


@pytest.mark.asyncio
async def test_search_filter_vault(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test filtering search by vault."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="test", vault="test_vault")
    results = await search_index.search(query)

    assert all(r.vault_name == "test_vault" for r in results.results)


@pytest.mark.asyncio
async def test_search_filter_project(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test filtering search by project."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="test", project="test-project")
    results = await search_index.search(query)

    assert all(r.project == "test-project" for r in results.results)


@pytest.mark.asyncio
async def test_search_filter_tags(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test filtering search by tags."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="test", tags=["authentication"])
    results = await search_index.search(query)

    assert all("authentication" in r.tags for r in results.results)


@pytest.mark.asyncio
async def test_search_sort_relevance(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test sorting by relevance."""
    await search_index.index_note(sample_note)

    query = SearchQuery(query="authentication", sort=SortOrder.RELEVANCE)
    results = await search_index.search(query)

    # Results should be ordered by score (descending)
    scores = [r.score for r in results.results]
    assert scores == sorted(scores, reverse=True)


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


@pytest.mark.asyncio
async def test_resolve_wikilink_exact(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test resolving wikilink with exact title match."""
    note_id = await search_index.index_note(sample_note)

    # Create another note to link to
    target_note = IndexedNote(
        vault_name="test_vault",
        relative_path="target.md",
        permalink="target",
        title="Target Note",
        note_type=NoteType.NOTE.value,
        content="Target content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        file_hash=compute_file_hash("Target content"),
    )
    target_id = await search_index.index_note(target_note)

    resolved = await search_index.resolve_wikilink("Target Note", from_vault="test_vault")

    assert resolved == target_id


@pytest.mark.asyncio
async def test_get_backlinks(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test getting backlinks to a note."""
    # Create target note
    target_note = IndexedNote(
        vault_name="test_vault",
        relative_path="target.md",
        permalink="target",
        title="Target Note",
        note_type=NoteType.NOTE.value,
        content="Target content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        file_hash=compute_file_hash("Target content"),
    )
    target_id = await search_index.index_note(target_note)

    # Create source note that links to target
    source_note = IndexedNote(
        vault_name="test_vault",
        relative_path="source.md",
        permalink="source",
        title="Source Note",
        note_type=NoteType.NOTE.value,
        content="Source content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[
            Wikilink(target="Target Note", line_number=1, column=0)
        ],
        file_hash=compute_file_hash("Source content"),
    )
    await search_index.index_note(source_note)

    backlinks = await search_index.get_backlinks(target_id)

    assert len(backlinks) >= 1
    assert any(b.title == "Source Note" for b in backlinks)


@pytest.mark.asyncio
async def test_list_tags(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test listing tags."""
    await search_index.index_note(sample_note)

    tags = await search_index.list_tags()

    assert len(tags) > 0
    tag_dict = dict(tags)
    assert "test" in tag_dict
    assert "authentication" in tag_dict


@pytest.mark.asyncio
async def test_list_projects(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test listing projects."""
    await search_index.index_note(sample_note)

    projects = await search_index.list_projects()

    assert len(projects) > 0
    project_dict = dict(projects)
    assert "test-project" in project_dict


@pytest.mark.asyncio
async def test_get_stats(search_index: SearchIndex, sample_note: IndexedNote) -> None:
    """Test getting index statistics."""
    await search_index.index_note(sample_note)

    stats = await search_index.get_stats()

    assert stats["total_notes"] >= 1
    assert "test_vault" in stats["notes_by_vault"]
    assert stats["total_observations"] >= 1
    assert stats["total_relations"] >= 1
    assert stats["total_tags"] >= 1


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
        "different_hash",
    )
    assert needs is True


@pytest.mark.asyncio
async def test_get_note_by_permalink(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test getting note by permalink."""
    await search_index.index_note(sample_note)

    note = await search_index.get_note_by_permalink("test-note")

    assert note is not None
    assert note.permalink == "test-note"


@pytest.mark.asyncio
async def test_get_note_by_path(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test getting note by path."""
    await search_index.index_note(sample_note)

    note = await search_index.get_note_by_path(
        "test_vault", "test-note.md"
    )

    assert note is not None
    assert note.relative_path == "test-note.md"


@pytest.mark.asyncio
async def test_get_recent_notes(
    search_index: SearchIndex, sample_note: IndexedNote
) -> None:
    """Test getting recent notes."""
    await search_index.index_note(sample_note)

    recent = await search_index.get_recent_notes(limit=10)

    assert len(recent) >= 1
    assert any(r.title == "Test Note" for r in recent)
