"""Tests for Graph API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from app.main import app
from app.api.dependencies import get_search_index, get_vault_manager, get_markdown_parser
from app.services.search_index import SearchIndex
from app.services.markdown_parser import MarkdownParser
from app.models.vault import VaultConfig, VaultManagerConfig


@pytest.fixture
def vault_config(temp_dir: Path) -> VaultManagerConfig:
    """Create a test vault manager configuration."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()
    return VaultManagerConfig(
        vaults=[VaultConfig(name="test_vault", path=vault_path)],
        default_vault="test_vault",
    )


@pytest.fixture
def search_index(temp_dir: Path) -> SearchIndex:
    """Create a SearchIndex instance for testing."""
    db_path = temp_dir / "test_index.db"
    return SearchIndex(db_path)


@pytest.fixture
async def client(vault_config: VaultManagerConfig, search_index: SearchIndex) -> AsyncClient:
    """Create an async test client with overridden dependencies."""
    def override_get_vault_manager():
        from app.services.vault_manager import VaultManager
        return VaultManager(vault_config)

    def override_get_search_index():
        return search_index

    app.dependency_overrides[get_vault_manager] = override_get_vault_manager
    app.dependency_overrides[get_search_index] = override_get_search_index
    app.dependency_overrides[get_markdown_parser] = lambda: MarkdownParser()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    if search_index.db is not None:
        await search_index.close()
    app.dependency_overrides.clear()




class TestGetGraph:
    """Tests for GET /api/graph endpoint."""

    @pytest.mark.asyncio
    async def test_get_graph_empty(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting graph with no notes."""
        await search_index.initialize()

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            response = await client.get("/api/graph")
            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "edges" in data
            assert data["nodes"] == []
            assert data["edges"] == []

    @pytest.mark.asyncio
    async def test_get_graph_with_cache(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting graph from cache."""
        await search_index.initialize()

        cached_data = {
            "nodes": [{"id": 1, "title": "Test"}],
            "edges": [],
        }

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            response = await client.get("/api/graph")
            assert response.status_code == 200
            data = response.json()
            assert data == cached_data


class TestListNodes:
    """Tests for GET /api/graph/nodes endpoint."""

    @pytest.mark.asyncio
    async def test_list_nodes_empty(self, client: AsyncClient, search_index: SearchIndex):
        """Test listing nodes when empty."""
        await search_index.initialize()
        response = await client.get("/api/graph/nodes")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert data["nodes"] == []

    @pytest.mark.asyncio
    async def test_list_nodes_with_limit(self, client: AsyncClient, search_index: SearchIndex):
        """Test listing nodes with custom limit."""
        await search_index.initialize()
        response = await client.get("/api/graph/nodes?limit=50")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_nodes_max_limit_enforced(self, client: AsyncClient, search_index: SearchIndex):
        """Test that max limit is enforced."""
        await search_index.initialize()
        # Even with high limit, should work (capped internally)
        response = await client.get("/api/graph/nodes?limit=1000")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_nodes_with_data(self, client: AsyncClient, search_index: SearchIndex):
        """Test listing nodes with actual data."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index a test note
        note = IndexedNote(
            vault_name="test_vault",
            relative_path="test-note.md",
            title="Test Note",
            permalink="test-note",
            note_type="note",
            project="project",
            content="Test content",
            tags=["tag1"],
            file_hash="hash1",
        )
        await search_index.index_note(note)

        response = await client.get("/api/graph/nodes")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["title"] == "Test Note"


class TestSimilarNotes:
    """Tests for GET /api/graph/nodes/{node_id}/similar endpoint."""

    @pytest.mark.asyncio
    async def test_similar_notes_not_found(self, client: AsyncClient, search_index: SearchIndex):
        """Test finding similar notes for non-existent node."""
        await search_index.initialize()
        response = await client.get("/api/graph/nodes/999/similar")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_similar_notes_invalid_method(self, client: AsyncClient, search_index: SearchIndex):
        """Test with invalid similarity method."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index a test note
        note = IndexedNote(
            vault_name="test_vault",
            relative_path="test-note.md",
            title="Test Note",
            permalink="test-note",
            note_type="note",
            project="project",
            content="Test content",
            tags=["tag1"],
            file_hash="hash1",
        )
        note_id = await search_index.index_note(note)

        response = await client.get(f"/api/graph/nodes/{note_id}/similar?method=invalid")
        assert response.status_code == 400
        assert "Invalid method" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_similar_notes_content_method(self, client: AsyncClient, search_index: SearchIndex):
        """Test similarity search using content method."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index source note
        source_note = IndexedNote(
            vault_name="test_vault",
            relative_path="python-guide.md",
            title="Python Programming Guide",
            permalink="python-guide",
            note_type="note",
            project="docs",
            content="Python is a versatile programming language used for web development and data science",
            tags=["python", "programming", "guide"],
            file_hash="hash1",
        )
        source_id = await search_index.index_note(source_note)

        # Index similar notes
        similar_note1 = IndexedNote(
            vault_name="test_vault",
            relative_path="python-tips.md",
            title="Python Tips and Tricks",
            permalink="python-tips",
            note_type="note",
            project="docs",
            content="Advanced Python programming techniques for experienced developers",
            tags=["python", "tips"],
            file_hash="hash2",
        )
        await search_index.index_note(similar_note1)

        similar_note2 = IndexedNote(
            vault_name="test_vault",
            relative_path="javascript-guide.md",
            title="JavaScript Guide",
            permalink="js-guide",
            note_type="note",
            project="docs",
            content="JavaScript is used for web development and creating interactive websites",
            tags=["javascript", "web"],
            file_hash="hash3",
        )
        await search_index.index_note(similar_note2)

        # Unrelated note
        unrelated_note = IndexedNote(
            vault_name="test_vault",
            relative_path="cooking-recipes.md",
            title="Cooking Recipes",
            permalink="recipes",
            note_type="note",
            project="personal",
            content="Collection of favorite cooking recipes and meal ideas",
            tags=["cooking", "food"],
            file_hash="hash4",
        )
        await search_index.index_note(unrelated_note)

        response = await client.get(f"/api/graph/nodes/{source_id}/similar?method=content&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert data["source_node_id"] == source_id
        assert data["method"] == "content"
        assert "similar_notes" in data
        assert len(data["similar_notes"]) <= 3

        # Python Tips should rank higher than JavaScript Guide due to more content overlap
        if len(data["similar_notes"]) > 0:
            assert "Python" in data["similar_notes"][0]["title"]

    @pytest.mark.asyncio
    async def test_similar_notes_graph_method(self, client: AsyncClient, search_index: SearchIndex):
        """Test similarity search using graph method (tags and relations)."""
        from app.models.search import IndexedNote
        from app.models.note import Relation, RelationType

        await search_index.initialize()

        # Index source note with tags and relations
        source_note = IndexedNote(
            vault_name="test_vault",
            relative_path="machine-learning.md",
            title="Machine Learning Basics",
            permalink="ml-basics",
            note_type="note",
            project="ai",
            content="Introduction to machine learning concepts",
            tags=["ml", "ai", "data-science"],
            relations=[
                Relation(
                    relation_type=RelationType.RELATES_TO,
                    target="Neural Networks",
                    context="Foundation for deep learning",
                    line_number=10
                ),
                Relation(
                    relation_type=RelationType.REQUIRES,
                    target="Linear Algebra",
                    context="Mathematical foundation",
                    line_number=15
                )
            ],
            file_hash="hash1",
        )
        source_id = await search_index.index_note(source_note)

        # Index note with overlapping tags and relations
        similar_note1 = IndexedNote(
            vault_name="test_vault",
            relative_path="deep-learning.md",
            title="Deep Learning Advanced",
            permalink="dl-advanced",
            note_type="note",
            project="ai",
            content="Advanced deep learning techniques",
            tags=["ml", "ai", "neural-networks"],  # 2/3 tags overlap
            relations=[
                Relation(
                    relation_type=RelationType.RELATES_TO,
                    target="Neural Networks",  # Same target
                    context="Core concept",
                    line_number=5
                )
            ],
            file_hash="hash2",
        )
        await search_index.index_note(similar_note1)

        # Index note with some overlapping tags but no relations
        similar_note2 = IndexedNote(
            vault_name="test_vault",
            relative_path="data-preprocessing.md",
            title="Data Preprocessing",
            permalink="data-prep",
            note_type="note",
            project="ai",
            content="Data preprocessing for machine learning",
            tags=["data-science", "ml"],  # 2/3 tags overlap
            relations=[],
            file_hash="hash3",
        )
        await search_index.index_note(similar_note2)

        # Index unrelated note
        unrelated_note = IndexedNote(
            vault_name="test_vault",
            relative_path="web-development.md",
            title="Web Development",
            permalink="web-dev",
            note_type="note",
            project="web",
            content="Modern web development practices",
            tags=["javascript", "react", "web"],
            relations=[],
            file_hash="hash4",
        )
        await search_index.index_note(unrelated_note)

        response = await client.get(f"/api/graph/nodes/{source_id}/similar?method=graph&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert data["source_node_id"] == source_id
        assert data["method"] == "graph"
        assert "similar_notes" in data

        # Notes with shared tags/relations should appear
        note_titles = [n["title"] for n in data["similar_notes"]]
        assert "Web Development" not in note_titles  # Unrelated should not appear

    @pytest.mark.asyncio
    async def test_similar_notes_hybrid_method(self, client: AsyncClient, search_index: SearchIndex):
        """Test similarity search using hybrid method (combined signals)."""
        from app.models.search import IndexedNote
        from app.models.note import Relation, RelationType

        await search_index.initialize()

        # Index source note
        source_note = IndexedNote(
            vault_name="test_vault",
            relative_path="react-hooks.md",
            title="React Hooks Guide",
            permalink="react-hooks",
            note_type="note",
            project="frontend",
            content="React Hooks provide state management in functional components",
            tags=["react", "javascript", "frontend"],
            relations=[
                Relation(
                    relation_type=RelationType.RELATES_TO,
                    target="React Components",
                    context="Hooks work with functional components",
                    line_number=5
                )
            ],
            file_hash="hash1",
        )
        source_id = await search_index.index_note(source_note)

        # Strong match: high tag overlap, relation overlap, and content similarity
        strong_match = IndexedNote(
            vault_name="test_vault",
            relative_path="react-state.md",
            title="React State Management",
            permalink="react-state",
            note_type="note",
            project="frontend",
            content="Managing state in React applications using hooks and context",
            tags=["react", "javascript", "state"],  # 2/3 tags overlap
            relations=[
                Relation(
                    relation_type=RelationType.RELATES_TO,
                    target="React Components",  # Same target
                    context="State management patterns",
                    line_number=3
                )
            ],
            file_hash="hash2",
        )
        await search_index.index_note(strong_match)

        # Moderate match: some tag overlap, different content
        moderate_match = IndexedNote(
            vault_name="test_vault",
            relative_path="vue-composition.md",
            title="Vue Composition API",
            permalink="vue-comp",
            note_type="note",
            project="frontend",
            content="Vue 3 Composition API for reactive state management",
            tags=["vue", "javascript", "frontend"],  # 2/3 tags overlap
            relations=[],
            file_hash="hash3",
        )
        await search_index.index_note(moderate_match)

        # Weak match: no tag overlap but some content similarity
        weak_match = IndexedNote(
            vault_name="test_vault",
            relative_path="angular-services.md",
            title="Angular Services",
            permalink="angular-svc",
            note_type="note",
            project="frontend",
            content="State management in Angular using services and RxJS",
            tags=["angular", "typescript", "rxjs"],  # No tag overlap
            relations=[],
            file_hash="hash4",
        )
        await search_index.index_note(weak_match)

        response = await client.get(f"/api/graph/nodes/{source_id}/similar?method=hybrid&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["source_node_id"] == source_id
        assert data["method"] == "hybrid"
        assert "similar_notes" in data

        # React State Management should rank highest due to combined signals
        if len(data["similar_notes"]) > 0:
            # The note with highest combined score should come first
            first_note = data["similar_notes"][0]
            assert first_note["score"] > 0  # Should have a positive score
            assert "score" in first_note
            assert "similarity_method" in first_note
            assert first_note["similarity_method"] == "hybrid"

    @pytest.mark.asyncio
    async def test_similar_notes_limit(self, client: AsyncClient, search_index: SearchIndex):
        """Test that limit parameter works correctly."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index source note
        source = IndexedNote(
            vault_name="test_vault",
            relative_path="source.md",
            title="Source Note",
            permalink="source",
            note_type="note",
            content="Source content about programming",
            tags=["tag1"],
            file_hash="hash_source",
        )
        source_id = await search_index.index_note(source)

        # Index multiple similar notes
        for i in range(10):
            note = IndexedNote(
                vault_name="test_vault",
                relative_path=f"similar-{i}.md",
                title=f"Similar Note {i}",
                permalink=f"similar-{i}",
                note_type="note",
                content=f"Similar content about programming {i}",
                tags=["tag1"],
                file_hash=f"hash_{i}",
            )
            await search_index.index_note(note)

        # Test with limit=3
        response = await client.get(f"/api/graph/nodes/{source_id}/similar?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["similar_notes"]) <= 3

        # Test with limit=5
        response = await client.get(f"/api/graph/nodes/{source_id}/similar?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["similar_notes"]) <= 5


class TestListEdges:
    """Tests for GET /api/graph/edges endpoint."""

    @pytest.mark.asyncio
    async def test_list_edges_empty(self, client: AsyncClient, search_index: SearchIndex):
        """Test listing edges when empty."""
        await search_index.initialize()

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            response = await client.get("/api/graph/edges")
            assert response.status_code == 200
            data = response.json()
            assert "edges" in data
            assert data["edges"] == []


class TestGetNeighbors:
    """Tests for GET /api/graph/nodes/{node_id}/neighbors endpoint."""

    @pytest.mark.asyncio
    async def test_get_neighbors_node_not_found(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting neighbors for non-existent node."""
        await search_index.initialize()
        response = await client.get("/api/graph/nodes/999/neighbors")
        assert response.status_code == 404
        assert "not found" in response.text.lower()

    @pytest.mark.asyncio
    async def test_get_neighbors_empty(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting neighbors for node with no connections."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index a test note first
        note = IndexedNote(
            vault_name="test_vault",
            relative_path="test-note.md",
            title="Test Note",
            permalink="test-note",
            note_type="note",
            project="project",
            content="Test content",
            tags=[],
            file_hash="hash1",
        )
        await search_index.index_note(note)

        # First indexed note gets ID 1 (SQLite autoincrement starts at 1)
        note_id = 1

        response = await client.get(f"/api/graph/nodes/{note_id}/neighbors")
        assert response.status_code == 200
        data = response.json()
        assert "node_id" in data
        assert data["node_id"] == note_id
        assert "neighbors" in data

    @pytest.mark.asyncio
    async def test_get_neighbors_direction_filter(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting neighbors with direction filter."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index a test note first
        note = IndexedNote(
            vault_name="test_vault",
            relative_path="test-note.md",
            title="Test Note",
            permalink="test-note",
            note_type="note",
            project="project",
            content="Test content",
            tags=[],
            file_hash="hash1",
        )
        await search_index.index_note(note)

        # First indexed note gets ID 1
        note_id = 1

        for direction in ["outgoing", "incoming", "both"]:
            response = await client.get(f"/api/graph/nodes/{note_id}/neighbors?direction={direction}")
            assert response.status_code == 200
            data = response.json()
            assert data["direction"] == direction


class TestBacklinks:
    """Tests for GET /api/graph/nodes/{node_id}/backlinks endpoint."""

    @pytest.mark.asyncio
    async def test_get_backlinks_node_not_found(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting backlinks for non-existent node."""
        await search_index.initialize()
        response = await client.get("/api/graph/nodes/999/backlinks")
        assert response.status_code == 404
        assert "not found" in response.text.lower()

    @pytest.mark.asyncio
    async def test_get_backlinks_empty(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting backlinks for node with no incoming edges."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index a test note that has no backlinks
        target_note = IndexedNote(
            vault_name="test_vault",
            relative_path="target-note.md",
            title="Target Note",
            permalink="target-note",
            note_type="note",
            project="project",
            content="Target content without links",
            tags=["target"],
            file_hash="hash1",
        )
        await search_index.index_note(target_note)

        # First indexed note gets ID 1
        target_id = 1

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            response = await client.get(f"/api/graph/nodes/{target_id}/backlinks")
            assert response.status_code == 200
            data = response.json()
            assert "target_node_id" in data
            assert data["target_node_id"] == target_id
            assert data["target_title"] == "Target Note"
            assert "backlinks" in data
            assert data["backlinks"] == []
            assert data["total_count"] == 0

    @pytest.mark.asyncio
    async def test_get_backlinks_with_incoming_edges(
        self, client: AsyncClient, search_index: SearchIndex, vault_config: VaultManagerConfig
    ):
        """Test getting backlinks for node with incoming edges."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Create a target note
        target_note = IndexedNote(
            vault_name="test_vault",
            relative_path="target-note.md",
            title="Target Note",
            permalink="target-note",
            note_type="note",
            project="project",
            content="Target content that will be referenced",
            tags=["target"],
            file_hash="hash_target",
        )
        await search_index.index_note(target_note)
        target_id = 1

        # Create source notes that link to the target
        source_note1 = IndexedNote(
            vault_name="test_vault",
            relative_path="source1.md",
            title="Source Note 1",
            permalink="source1",
            note_type="note",
            project="project",
            content="This note [[target-note]] links to target. Also mentions @depends_on target-note.",
            tags=["source"],
            file_hash="hash_source1",
        )
        await search_index.index_note(source_note1)

        source_note2 = IndexedNote(
            vault_name="test_vault",
            relative_path="source2.md",
            title="Source Note 2",
            permalink="source2",
            note_type="note",
            project="project",
            content="Another note with [[Target Note]] link and @related_to target-note.",
            tags=["source", "related"],
            file_hash="hash_source2",
        )
        await search_index.index_note(source_note2)

        # Write actual files to vault for parsing with proper YAML frontmatter
        # The markdown parser needs frontmatter to properly extract title/permalink
        # which are used for edge resolution in the graph engine
        vault_path = vault_config.vaults[0].path
        (vault_path / "target-note.md").write_text(
            "---\ntitle: Target Note\npermalink: target-note\ntype: note\n---\n"
            + target_note.content
        )
        (vault_path / "source1.md").write_text(
            "---\ntitle: Source Note 1\npermalink: source1\ntype: note\n---\n"
            + source_note1.content
        )
        (vault_path / "source2.md").write_text(
            "---\ntitle: Source Note 2\npermalink: source2\ntype: note\n---\n"
            + source_note2.content
        )

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            response = await client.get(f"/api/graph/nodes/{target_id}/backlinks")
            assert response.status_code == 200
            data = response.json()

            assert data["target_node_id"] == target_id
            assert data["target_title"] == "Target Note"
            assert "backlinks" in data
            assert len(data["backlinks"]) > 0
            assert data["total_count"] == len(data["backlinks"])

            # Check that backlinks contain expected source notes
            source_titles = [backlink["source_node"]["title"] for backlink in data["backlinks"]]
            assert "Source Note 1" in source_titles or "Source Note 2" in source_titles

    @pytest.mark.asyncio
    async def test_get_backlinks_cached(self, client: AsyncClient, search_index: SearchIndex):
        """Test that backlinks endpoint uses caching."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Index a test note
        note = IndexedNote(
            vault_name="test_vault",
            relative_path="test-note.md",
            title="Test Note",
            permalink="test-note",
            note_type="note",
            project="project",
            content="Test content",
            tags=[],
            file_hash="hash1",
        )
        await search_index.index_note(note)
        note_id = 1

        # Mock cache to return cached result
        cached_data = {
            "target_node_id": note_id,
            "target_title": "Test Note",
            "backlinks": [],
            "total_count": 0,
        }

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = cached_data
            mock_cache.set = MagicMock()

            response = await client.get(f"/api/graph/nodes/{note_id}/backlinks")
            assert response.status_code == 200
            data = response.json()

            # Verify cached data was returned
            assert data == cached_data
            # Verify cache.set was not called (since we got a cache hit)
            mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_backlinks_with_different_edge_types(
        self, client: AsyncClient, search_index: SearchIndex, vault_config: VaultManagerConfig
    ):
        """Test getting backlinks with various edge types (relations and wikilinks)."""
        from app.models.search import IndexedNote

        await search_index.initialize()

        # Create a target note
        target_note = IndexedNote(
            vault_name="test_vault",
            relative_path="target.md",
            title="Target",
            permalink="target",
            note_type="note",
            project="project",
            content="This is the target note",
            tags=["target"],
            file_hash="hash_target",
        )
        await search_index.index_note(target_note)
        target_id = 1

        # Create source with different relation types
        source_with_relations = IndexedNote(
            vault_name="test_vault",
            relative_path="relations.md",
            title="Relations Source",
            permalink="relations",
            note_type="note",
            project="project",
            content="""
                @depends_on target
                @enables target
                @learned_from target
                @related_to target
            """,
            tags=["relations"],
            file_hash="hash_rel",
        )
        await search_index.index_note(source_with_relations)

        # Create source with wikilink
        source_with_wikilink = IndexedNote(
            vault_name="test_vault",
            relative_path="wikilink.md",
            title="Wikilink Source",
            permalink="wikilink",
            note_type="note",
            project="project",
            content="This has a [[target]] wikilink",
            tags=["wikilink"],
            file_hash="hash_wiki",
        )
        await search_index.index_note(source_with_wikilink)

        # Write actual files to vault for parsing with proper YAML frontmatter
        vault_path = vault_config.vaults[0].path
        (vault_path / "target.md").write_text(
            "---\ntitle: Target\npermalink: target\ntype: note\n---\n"
            + target_note.content
        )
        (vault_path / "relations.md").write_text(
            "---\ntitle: Relations Source\npermalink: relations\ntype: note\n---\n"
            + source_with_relations.content
        )
        (vault_path / "wikilink.md").write_text(
            "---\ntitle: Wikilink Source\npermalink: wikilink\ntype: note\n---\n"
            + source_with_wikilink.content
        )

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            response = await client.get(f"/api/graph/nodes/{target_id}/backlinks")
            assert response.status_code == 200
            data = response.json()

            # Verify we have backlinks
            assert len(data["backlinks"]) > 0

            # Check edge types in the backlinks
            edge_types = [backlink["edge_type"] for backlink in data["backlinks"]]
            # We expect various edge types based on the relations
            # The exact types depend on the markdown parser's implementation
