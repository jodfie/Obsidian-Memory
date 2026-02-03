"""Tests for WikilinkResolver service."""

from datetime import datetime

import pytest

from app.models.note import NoteType, ParsedNote, Wikilink
from app.models.search import IndexedNote
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex, compute_file_hash
from app.services.wikilink_resolver import WikilinkResolver


@pytest.fixture
async def search_index(temp_dir) -> SearchIndex:
    """Create a SearchIndex instance for testing."""
    db_path = temp_dir / "test_index.db"
    index = SearchIndex(db_path)
    await index.initialize()
    yield index
    await index.close()


@pytest.fixture
def markdown_parser() -> MarkdownParser:
    """Create a MarkdownParser instance."""
    return MarkdownParser()


@pytest.fixture
def wikilink_resolver(
    markdown_parser: MarkdownParser, search_index: SearchIndex
) -> WikilinkResolver:
    """Create a WikilinkResolver instance."""
    return WikilinkResolver(markdown_parser, search_index)


@pytest.fixture
async def sample_note(search_index: SearchIndex) -> tuple[IndexedNote, ParsedNote]:
    """Create and index a sample note."""
    from app.models.note import Frontmatter

    indexed = IndexedNote(
        vault_name="test_vault",
        relative_path="test-note.md",
        permalink="test-note",
        title="Test Note",
        note_type="note",
        project=None,
        content="Test content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=datetime(2025, 1, 15, 10, 30, 0),
        updated_at=datetime(2025, 1, 16, 14, 20, 0),
        file_hash=compute_file_hash("test"),
    )

    parsed = ParsedNote(
        frontmatter=Frontmatter(
            title="Test Note", permalink="test-note", type=NoteType.NOTE
        ),
        observations=[],
        relations=[],
        wikilinks=[],
        raw_content="Test content",
        headings=[],
    )

    note_id = await search_index.index_note(indexed)
    # Update the indexed note with the ID
    # Note: IndexedNote doesn't have id field, so we'll track it separately
    return (indexed, parsed, note_id)


@pytest.mark.asyncio
async def test_extract_wikilinks(
    wikilink_resolver: WikilinkResolver,
) -> None:
    """Test extracting wikilinks from content."""
    content = """
This is a note with [[Linked Note]] and [[Another Note|display text]].
Also has [[folder/Path Note]].
"""
    wikilinks = await wikilink_resolver.extract_wikilinks(content)

    assert len(wikilinks) == 3
    assert wikilinks[0].target == "Linked Note"
    assert wikilinks[1].target == "Another Note"
    assert wikilinks[1].display_text == "display text"
    assert wikilinks[2].target == "Path Note"
    assert wikilinks[2].path == "folder"


@pytest.mark.asyncio
async def test_resolve_wikilink_exact_match(
    wikilink_resolver: WikilinkResolver,
    search_index: SearchIndex,
) -> None:
    """Test resolving wikilink with exact title match."""
    from app.models.note import Frontmatter

    # Index a note
    indexed = IndexedNote(
        vault_name="test_vault",
        relative_path="target.md",
        permalink="target",
        title="Target Note",
        note_type="note",
        project=None,
        content="Target content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash=compute_file_hash("target"),
    )

    parsed = ParsedNote(
        frontmatter=Frontmatter(title="Target Note", permalink="target"),
        observations=[],
        relations=[],
        wikilinks=[],
        raw_content="",
        headings=[],
    )

    target_id = await search_index.index_note(indexed)

    # Resolve wikilink
    wikilink = Wikilink(
        target="Target Note",
        display_text=None,
        path=None,
        line_number=1,
        column=0,
    )

    result = await wikilink_resolver.resolve_wikilink(
        wikilink, "test_vault"
    )

    assert result.resolved_id == target_id
    assert result.resolution_method is not None


@pytest.mark.asyncio
async def test_resolve_wikilink_permalink(
    wikilink_resolver: WikilinkResolver,
    search_index: SearchIndex,
) -> None:
    """Test resolving wikilink by permalink."""
    from app.models.note import Frontmatter

    # Index a note
    indexed = IndexedNote(
        vault_name="test_vault",
        relative_path="target.md",
        permalink="target-note",
        title="Target Note",
        note_type="note",
        project=None,
        content="Target content",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash=compute_file_hash("target"),
    )

    parsed = ParsedNote(
        frontmatter=Frontmatter(title="Target Note", permalink="target-note"),
        observations=[],
        relations=[],
        wikilinks=[],
        raw_content="",
        headings=[],
    )

    target_id = await search_index.index_note(indexed)

    # Resolve wikilink by permalink
    wikilink = Wikilink(
        target="target-note",
        display_text=None,
        path=None,
        line_number=1,
        column=0,
    )

    result = await wikilink_resolver.resolve_wikilink(wikilink)

    assert result.resolved_id == target_id


@pytest.mark.asyncio
async def test_resolve_wikilinks_batch(
    wikilink_resolver: WikilinkResolver,
    search_index: SearchIndex,
) -> None:
    """Test batch resolution of wikilinks."""
    from app.models.note import Frontmatter

    # Index target notes
    for i, title in enumerate(["Note 1", "Note 2"], start=1):
        indexed = IndexedNote(
            vault_name="test_vault",
            relative_path=f"note{i}.md",
            permalink=f"note-{i}",
            title=title,
            note_type="note",
            project=None,
            content="",
            tags=[],
            observations=[],
            relations=[],
            wikilinks=[],
            created_at=None,
            updated_at=None,
            file_hash=compute_file_hash(f"note{i}"),
        )
        await search_index.index_note(indexed)

    # Resolve multiple wikilinks
    wikilinks = [
        Wikilink(
            target="Note 1",
            display_text=None,
            path=None,
            line_number=1,
            column=0,
        ),
        Wikilink(
            target="Note 2",
            display_text=None,
            path=None,
            line_number=2,
            column=0,
        ),
        Wikilink(
            target="Non-existent",
            display_text=None,
            path=None,
            line_number=3,
            column=0,
        ),
    ]

    results = await wikilink_resolver.resolve_wikilinks(
        wikilinks, "test_vault"
    )

    assert len(results) == 3
    assert results[0].resolved_id is not None
    assert results[1].resolved_id is not None
    assert results[2].resolved_id is None  # Broken link


@pytest.mark.asyncio
async def test_get_broken_links(
    wikilink_resolver: WikilinkResolver,
    search_index: SearchIndex,
) -> None:
    """Test getting broken (unresolved) links."""
    from app.models.note import Frontmatter

    indexed = IndexedNote(
        vault_name="test_vault",
        relative_path="source.md",
        permalink="source",
        title="Source Note",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[
            Wikilink(
                target="Existing Note",
                display_text=None,
                path=None,
                line_number=1,
                column=0,
            ),
            Wikilink(
                target="Broken Link",
                display_text=None,
                path=None,
                line_number=2,
                column=0,
            ),
        ],
        created_at=None,
        updated_at=None,
        file_hash=compute_file_hash("source"),
    )

    parsed = ParsedNote(
        frontmatter=Frontmatter(title="Source Note", permalink="source"),
        observations=[],
        relations=[],
        wikilinks=indexed.wikilinks,
        raw_content="",
        headings=[],
    )

    # Index the existing note
    existing = IndexedNote(
        vault_name="test_vault",
        relative_path="existing.md",
        permalink="existing",
        title="Existing Note",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash=compute_file_hash("existing"),
    )
    await search_index.index_note(existing)

    broken = await wikilink_resolver.get_broken_links(parsed, indexed)

    assert len(broken) == 1
    assert broken[0].target == "Broken Link"


@pytest.mark.asyncio
async def test_resolve_wikilinks_batch_same_as_individual(
    wikilink_resolver: WikilinkResolver,
    search_index: SearchIndex,
) -> None:
    """Batch resolution returns same results as resolving one-by-one."""
    from app.models.note import Frontmatter

    for i, title in enumerate(["A", "B", "C"], start=1):
        indexed = IndexedNote(
            vault_name="test_vault",
            relative_path=f"n{i}.md",
            permalink=f"n-{i}",
            title=title,
            note_type="note",
            project=None,
            content="",
            tags=[],
            observations=[],
            relations=[],
            wikilinks=[],
            created_at=None,
            updated_at=None,
            file_hash=compute_file_hash(f"n{i}"),
        )
        await search_index.index_note(indexed)

    wikilinks = [
        Wikilink(target="A", display_text=None, path=None, line_number=1, column=0),
        Wikilink(target="B", display_text=None, path=None, line_number=2, column=0),
        Wikilink(target="Missing", display_text=None, path=None, line_number=3, column=0),
    ]

    batch_results = await wikilink_resolver.resolve_wikilinks(wikilinks, "test_vault")
    individual_results = []
    for w in wikilinks:
        r = await wikilink_resolver.resolve_wikilink(w, "test_vault")
        individual_results.append(r)

    assert len(batch_results) == 3
    for b, i in zip(batch_results, individual_results):
        assert b.resolved_id == i.resolved_id
        assert b.wikilink.target == i.wikilink.target


@pytest.mark.asyncio
async def test_resolve_cache_invalidation(
    wikilink_resolver: WikilinkResolver,
    search_index: SearchIndex,
) -> None:
    """Clear resolve cache and verify next resolve hits DB again."""
    from app.models.note import Frontmatter

    indexed = IndexedNote(
        vault_name="test_vault",
        relative_path="cached.md",
        permalink="cached",
        title="Cached Note",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash=compute_file_hash("cached"),
    )
    note_id = await search_index.index_note(indexed)
    wikilink = Wikilink(
        target="Cached Note",
        display_text=None,
        path=None,
        line_number=1,
        column=0,
    )

    r1 = await wikilink_resolver.resolve_wikilink(wikilink, "test_vault")
    assert r1.resolved_id == note_id

    wikilink_resolver.clear_resolve_cache()
    r2 = await wikilink_resolver.resolve_wikilink(wikilink, "test_vault")
    assert r2.resolved_id == note_id
