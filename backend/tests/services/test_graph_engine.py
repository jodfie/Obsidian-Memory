"""Tests for GraphEngine service."""

from datetime import datetime

import pytest

from app.models.graph import EdgeType, Graph
from app.models.note import (
    NoteType,
    Observation,
    ObservationCategory,
    ParsedNote,
    Relation,
    RelationType,
    Wikilink,
)
from app.models.search import IndexedNote
from app.services.graph_engine import GraphEngine
from app.services.search_index import compute_file_hash


@pytest.fixture
def graph_engine() -> GraphEngine:
    """Create a GraphEngine instance."""
    return GraphEngine()


@pytest.fixture
def sample_indexed_note() -> IndexedNote:
    """Create a sample indexed note."""
    return IndexedNote(
        vault_name="test_vault",
        relative_path="test-note.md",
        permalink="test-note",
        title="Test Note",
        note_type="note",
        project="test-project",
        content="Test content",
        tags=["test"],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=datetime(2025, 1, 15, 10, 30, 0),
        updated_at=datetime(2025, 1, 16, 14, 20, 0),
        file_hash=compute_file_hash("test"),
    )


@pytest.fixture
def sample_parsed_note() -> ParsedNote:
    """Create a sample parsed note."""
    from app.models.note import Frontmatter

    return ParsedNote(
        frontmatter=Frontmatter(
            title="Test Note",
            type=NoteType.NOTE,
            project="test-project",
            permalink="test-note",
            tags=["test"],
        ),
        observations=[],
        relations=[],
        wikilinks=[],
        raw_content="Test content",
        headings=[],
    )


@pytest.mark.asyncio
async def test_add_note_creates_node(
    graph_engine: GraphEngine,
    sample_indexed_note: IndexedNote,
    sample_parsed_note: ParsedNote,
) -> None:
    """Test that adding a note creates a node."""
    graph_engine.add_note(1, sample_indexed_note, sample_parsed_note)

    node = graph_engine.get_node(1)
    assert node is not None
    assert node.title == "Test Note"
    assert node.permalink == "test-note"
    assert node.vault_name == "test_vault"


@pytest.mark.asyncio
async def test_add_note_updates_mappings(
    graph_engine: GraphEngine,
    sample_indexed_note: IndexedNote,
    sample_parsed_note: ParsedNote,
) -> None:
    """Test that adding a note updates title and permalink mappings."""
    graph_engine.add_note(1, sample_indexed_note, sample_parsed_note)

    assert graph_engine.graph.title_to_id["Test Note"] == 1
    assert graph_engine.graph.permalink_to_id["test-note"] == 1


@pytest.mark.asyncio
async def test_add_note_with_relations_creates_edges(
    graph_engine: GraphEngine,
    sample_indexed_note: IndexedNote,
) -> None:
    """Test that adding a note with relations creates edges."""
    from app.models.note import Frontmatter

    parsed_note = ParsedNote(
        frontmatter=Frontmatter(title="Test Note", permalink="test-note"),
        observations=[],
        relations=[
            Relation(
                relation_type=RelationType.DEPENDS_ON,
                target="Other Note",
                target_path=None,
                context=None,
                line_number=1,
            )
        ],
        wikilinks=[],
        raw_content="",
        headings=[],
    )

    graph_engine.add_note(1, sample_indexed_note, parsed_note)

    edges = graph_engine.get_outgoing_edges(1)
    assert len(edges) == 1
    assert edges[0].edge_type == EdgeType.DEPENDS_ON
    assert edges[0].target_title == "Other Note"


@pytest.mark.asyncio
async def test_add_note_with_wikilinks_creates_edges(
    graph_engine: GraphEngine,
    sample_indexed_note: IndexedNote,
) -> None:
    """Test that adding a note with wikilinks creates edges."""
    from app.models.note import Frontmatter

    parsed_note = ParsedNote(
        frontmatter=Frontmatter(title="Test Note", permalink="test-note"),
        observations=[],
        relations=[],
        wikilinks=[
            Wikilink(
                target="Linked Note",
                display_text=None,
                path=None,
                line_number=1,
                column=0,
            )
        ],
        raw_content="",
        headings=[],
    )

    graph_engine.add_note(1, sample_indexed_note, parsed_note)

    edges = graph_engine.get_outgoing_edges(1)
    assert len(edges) == 1
    assert edges[0].edge_type == EdgeType.LINKS_TO
    assert edges[0].target_title == "Linked Note"
    assert edges[0].weight == 0.5  # Wikilinks have lower weight


@pytest.mark.asyncio
async def test_resolve_edges(
    graph_engine: GraphEngine,
) -> None:
    """Test that resolve_edges resolves target IDs."""
    from app.models.note import Frontmatter

    # Add first note
    note1 = IndexedNote(
        id=1,
        vault_name="test_vault",
        relative_path="note1.md",
        permalink="note1",
        title="Note 1",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash="",
    )
    parsed1 = ParsedNote(
        frontmatter=Frontmatter(title="Note 1", permalink="note1"),
        observations=[],
        relations=[],
        wikilinks=[],
        raw_content="",
        headings=[],
    )
    graph_engine.add_note(1, note1, parsed1)

    # Add second note that links to first
    note2 = IndexedNote(
        vault_name="test_vault",
        relative_path="note2.md",
        permalink="note2",
        title="Note 2",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[
            Relation(
                relation_type=RelationType.DEPENDS_ON,
                target="Note 1",
                target_path=None,
                context=None,
                line_number=1,
            )
        ],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash="",
    )
    parsed2 = ParsedNote(
        frontmatter=Frontmatter(title="Note 2", permalink="note2"),
        observations=[],
        relations=parsed2.relations if 'parsed2' in locals() else [],
        wikilinks=[],
        raw_content="",
        headings=[],
    )
    # Fix: use the relations from note2
    parsed2.relations = note2.relations
    graph_engine.add_note(2, note2, parsed2)

    # Resolve edges
    graph_engine.resolve_edges()

    # Check that edge is resolved
    edges = graph_engine.get_outgoing_edges(2)
    assert len(edges) == 1
    assert edges[0].target_id == 1


@pytest.mark.asyncio
async def test_remove_note(
    graph_engine: GraphEngine,
    sample_indexed_note: IndexedNote,
    sample_parsed_note: ParsedNote,
) -> None:
    """Test that removing a note removes it and its edges."""
    graph_engine.add_note(1, sample_indexed_note, sample_parsed_note)

    assert graph_engine.get_node(1) is not None

    graph_engine.remove_note(1)

    assert graph_engine.get_node(1) is None
    assert "Test Note" not in graph_engine.graph.title_to_id
    assert "test-note" not in graph_engine.graph.permalink_to_id


@pytest.mark.asyncio
async def test_get_neighbors(
    graph_engine: GraphEngine,
) -> None:
    """Test getting neighbor nodes."""
    from app.models.note import Frontmatter

    # Create three connected notes
    note1 = IndexedNote(
        vault_name="test_vault",
        relative_path="note1.md",
        permalink="note1",
        title="Note 1",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash="",
    )
    parsed1 = ParsedNote(
        frontmatter=Frontmatter(title="Note 1", permalink="note1"),
        observations=[],
        relations=[],
        wikilinks=[],
        raw_content="",
        headings=[],
    )
    graph_engine.add_note(1, note1, parsed1)

    note2 = IndexedNote(
        id=2,
        vault_name="test_vault",
        relative_path="note2.md",
        permalink="note2",
        title="Note 2",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[
            Relation(
                relation_type=RelationType.DEPENDS_ON,
                target="Note 1",
                target_path=None,
                context=None,
                line_number=1,
            )
        ],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash="",
    )
    parsed2 = ParsedNote(
        frontmatter=Frontmatter(title="Note 2", permalink="note2"),
        observations=[],
        relations=note2.relations,
        wikilinks=[],
        raw_content="",
        headings=[],
    )
    graph_engine.add_note(2, note2, parsed2)

    graph_engine.resolve_edges()

    neighbors = graph_engine.get_neighbors(1)
    assert 2 in neighbors

    neighbors = graph_engine.get_neighbors(2)
    assert 1 in neighbors


@pytest.mark.asyncio
async def test_get_incoming_edges(
    graph_engine: GraphEngine,
) -> None:
    """Test getting incoming edges."""
    from app.models.note import Frontmatter

    note1 = IndexedNote(
        vault_name="test_vault",
        relative_path="note1.md",
        permalink="note1",
        title="Note 1",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash="",
    )
    parsed1 = ParsedNote(
        frontmatter=Frontmatter(title="Note 1", permalink="note1"),
        observations=[],
        relations=[],
        wikilinks=[],
        raw_content="",
        headings=[],
    )
    graph_engine.add_note(1, note1, parsed1)

    note2 = IndexedNote(
        vault_name="test_vault",
        relative_path="note2.md",
        permalink="note2",
        title="Note 2",
        note_type="note",
        project=None,
        content="",
        tags=[],
        observations=[],
        relations=[
            Relation(
                relation_type=RelationType.DEPENDS_ON,
                target="Note 1",
                target_path=None,
                context=None,
                line_number=1,
            )
        ],
        wikilinks=[],
        created_at=None,
        updated_at=None,
        file_hash="",
    )
    parsed2 = ParsedNote(
        frontmatter=Frontmatter(title="Note 2", permalink="note2"),
        observations=[],
        relations=note2.relations,
        wikilinks=[],
        raw_content="",
        headings=[],
    )
    graph_engine.add_note(2, note2, parsed2)

    graph_engine.resolve_edges()

    incoming = graph_engine.get_incoming_edges(1)
    assert len(incoming) == 1
    assert incoming[0].source_id == 2
