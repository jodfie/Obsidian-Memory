"""Tests for Graph Statistics and Analysis API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from app.main import app
from app.api.dependencies import get_search_index, get_vault_manager, get_markdown_parser
from app.services.search_index import SearchIndex
from app.services.vault_manager import VaultManager
from app.services.markdown_parser import MarkdownParser
from app.models.vault import VaultConfig, VaultManagerConfig
from app.models.search import SearchResult


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
def vault_manager(vault_config: VaultManagerConfig) -> VaultManager:
    """Create a VaultManager instance for testing."""
    return VaultManager(vault_config)


@pytest.fixture
def search_index(temp_dir: Path) -> SearchIndex:
    """Create a SearchIndex instance for testing."""
    db_path = temp_dir / "test_index.db"
    return SearchIndex(db_path)


@pytest.fixture
async def client(vault_config: VaultManagerConfig, search_index: SearchIndex) -> AsyncClient:
    """Create an async test client with overridden dependencies."""
    def override_get_vault_manager():
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


class TestGraphStats:
    """Tests for GET /api/graph/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_graph_stats_empty(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting graph stats with no notes."""
        await search_index.initialize()

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            response = await client.get("/api/graph/stats")
            assert response.status_code == 200
            data = response.json()

            # Check all required fields
            assert data["total_nodes"] == 0
            assert data["total_edges"] == 0
            assert data["edge_type_distribution"] == {}
            assert data["orphan_nodes"] == []
            assert data["orphan_count"] == 0
            assert data["average_degree"] == 0.0
            assert data["graph_density"] == 0.0
            assert data["top_hubs"] == []

    @pytest.mark.asyncio
    async def test_get_graph_stats_with_nodes(
        self,
        client: AsyncClient,
        search_index: SearchIndex,
        vault_manager: VaultManager,
        vault_config: VaultManagerConfig,
    ):
        """Test getting graph stats with multiple nodes and edges."""
        await search_index.initialize()

        # Create test notes with various connections
        vault_path = vault_config.vaults[0].path

        # Hub note - connected to many others
        hub_note = vault_path / "hub_note.md"
        hub_note.write_text("""---
title: Central Hub
permalink: central-hub
type: note
---
# Central Hub

This is a hub note with many connections.

- depends_on [[Note A]]
- enables [[Note B]]
- related_to [[Note C]]

Also links to [[Note D]] and [[Note E]].
""")

        # Regular notes with some connections
        note_a = vault_path / "note_a.md"
        note_a.write_text("""---
title: Note A
permalink: note-a
type: note
---
# Note A

- part_of [[Central Hub]]
- related_to [[Note B]]
""")

        note_b = vault_path / "note_b.md"
        note_b.write_text("""---
title: Note B
permalink: note-b
type: note
---
# Note B

Links to [[Central Hub]].
""")

        # Orphan note - no connections
        orphan_note = vault_path / "orphan_note.md"
        orphan_note.write_text("""---
title: Orphan Note
permalink: orphan-note
type: note
---
# Orphan Note

This note has no connections to other notes.
""")

        # Index the notes
        await vault_manager.index_vault("test_vault")
        search_results = await search_index.search({"query": ""})

        # Mock the search results
        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()

            response = await client.get("/api/graph/stats")
            assert response.status_code == 200
            data = response.json()

            # Verify stats structure
            assert data["total_nodes"] >= 3  # At least hub, note_a, note_b, orphan
            assert data["total_edges"] > 0  # Should have edges from relations and wikilinks
            assert "edge_type_distribution" in data
            assert "orphan_nodes" in data
            assert data["average_degree"] > 0  # Should have some connectivity
            assert "top_hubs" in data
            assert len(data["top_hubs"]) > 0  # Should have at least the hub node

    @pytest.mark.asyncio
    async def test_get_graph_stats_cached(self, client: AsyncClient, search_index: SearchIndex):
        """Test getting graph stats from cache."""
        await search_index.initialize()

        cached_stats = {
            "total_nodes": 10,
            "total_edges": 15,
            "edge_type_distribution": {"depends_on": 5, "links_to": 10},
            "orphan_nodes": [3, 7],
            "orphan_count": 2,
            "average_degree": 3.0,
            "graph_density": 0.167,
            "top_hubs": [
                {"node_id": 1, "degree": 8},
                {"node_id": 2, "degree": 6},
            ],
        }

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = cached_stats

            response = await client.get("/api/graph/stats")
            assert response.status_code == 200
            data = response.json()
            assert data == cached_stats


class TestNodeCentrality:
    """Tests for GET /api/graph/nodes/{id}/centrality endpoint."""

    @pytest.mark.asyncio
    async def test_get_centrality_node_not_found(
        self, client: AsyncClient, search_index: SearchIndex
    ):
        """Test getting centrality for non-existent node."""
        await search_index.initialize()

        with patch("app.api.graph.cache") as mock_cache:
            mock_cache.get.return_value = None

            response = await client.get("/api/graph/nodes/999/centrality")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_centrality_isolated_node(
        self,
        client: AsyncClient,
        search_index: SearchIndex,
        vault_manager: VaultManager,
        vault_config: VaultManagerConfig,
    ):
        """Test getting centrality for an isolated node (no connections)."""
        await search_index.initialize()

        # Create an isolated note
        vault_path = vault_config.vaults[0].path
        isolated_note = vault_path / "isolated.md"
        isolated_note.write_text("""---
title: Isolated Note
permalink: isolated
type: note
---
# Isolated Note

No connections here.
""")

        # Index the note
        await vault_manager.index_vault("test_vault")
        search_results = await search_index.search({"query": "Isolated"})

        if search_results.results:
            node_id = search_results.results[0].note_id

            with patch("app.api.graph.cache") as mock_cache:
                mock_cache.get.return_value = None
                mock_cache.set = MagicMock()

                response = await client.get(f"/api/graph/nodes/{node_id}/centrality")
                assert response.status_code == 200
                data = response.json()

                # Verify centrality metrics for isolated node
                assert data["node_id"] == node_id
                assert data["title"] == "Isolated Note"
                assert data["degree_centrality"] == 0
                assert data["in_degree"] == 0
                assert data["out_degree"] == 0
                assert data["normalized_centrality"] == 0.0
                assert data["outgoing_by_type"] == {}
                assert data["incoming_by_type"] == {}

    @pytest.mark.asyncio
    async def test_get_centrality_hub_node(
        self,
        client: AsyncClient,
        search_index: SearchIndex,
        vault_manager: VaultManager,
        vault_config: VaultManagerConfig,
    ):
        """Test getting centrality for a well-connected hub node."""
        await search_index.initialize()

        # Create a hub note with many connections
        vault_path = vault_config.vaults[0].path

        hub_note = vault_path / "knowledge_hub.md"
        hub_note.write_text("""---
title: Knowledge Hub
permalink: knowledge-hub
type: note
---
# Knowledge Hub

This is a central hub with many connections.

## Relations
- depends_on [[Foundation]]
- enables [[Feature A]]
- enables [[Feature B]]
- related_to [[Topic X]]
- related_to [[Topic Y]]
- part_of [[System]]

## References
See also [[Reference 1]], [[Reference 2]], and [[Reference 3]].
""")

        # Create notes that link back to the hub
        note1 = vault_path / "feature_a.md"
        note1.write_text("""---
title: Feature A
permalink: feature-a
type: note
---
# Feature A

- depends_on [[Knowledge Hub]]
""")

        note2 = vault_path / "feature_b.md"
        note2.write_text("""---
title: Feature B
permalink: feature-b
type: note
---
# Feature B

This feature is enabled by [[Knowledge Hub]].
""")

        # Index all notes
        await vault_manager.index_vault("test_vault")
        search_results = await search_index.search({"query": "Knowledge Hub"})

        if search_results.results:
            hub_id = search_results.results[0].note_id

            with patch("app.api.graph.cache") as mock_cache:
                mock_cache.get.return_value = None
                mock_cache.set = MagicMock()

                response = await client.get(f"/api/graph/nodes/{hub_id}/centrality")
                assert response.status_code == 200
                data = response.json()

                # Verify centrality metrics for hub node
                assert data["node_id"] == hub_id
                assert data["title"] == "Knowledge Hub"
                assert data["degree_centrality"] > 0  # Should have connections
                assert data["out_degree"] > 0  # Has outgoing edges
                # May or may not have incoming edges depending on graph building
                assert data["normalized_centrality"] > 0.0

                # Check edge type distribution
                if data["out_degree"] > 0:
                    assert len(data["outgoing_by_type"]) > 0
                    # Should have various edge types from relations

    @pytest.mark.asyncio
    async def test_get_centrality_cached(
        self, client: AsyncClient, search_index: SearchIndex
    ):
        """Test getting centrality from cache."""
        await search_index.initialize()

        # Create a mock note that exists
        with patch.object(search_index, "get_note_by_id") as mock_get_note:
            mock_get_note.return_value = MagicMock(
                note_id=1,
                title="Test Note",
                permalink="test-note",
            )

            cached_centrality = {
                "node_id": 1,
                "title": "Test Note",
                "permalink": "test-note",
                "degree_centrality": 5,
                "in_degree": 2,
                "out_degree": 3,
                "normalized_centrality": 0.5,
                "outgoing_by_type": {"depends_on": 2, "links_to": 1},
                "incoming_by_type": {"enables": 1, "links_to": 1},
            }

            with patch("app.api.graph.cache") as mock_cache:
                mock_cache.get.return_value = cached_centrality

                response = await client.get("/api/graph/nodes/1/centrality")
                assert response.status_code == 200
                data = response.json()
                assert data == cached_centrality


class TestGraphEngineIntegration:
    """Integration tests for GraphEngine analysis methods."""

    def test_graph_stats_calculation(self):
        """Test graph statistics calculation logic."""
        from app.services.graph_engine import GraphEngine
        from app.models.graph import Node, Edge, EdgeType

        engine = GraphEngine()

        # Add nodes
        for i in range(5):
            node = Node(
                id=i,
                title=f"Node {i}",
                vault_name="test",
                relative_path=f"node_{i}.md",
                note_type="note",
            )
            engine.graph.nodes[i] = node
            engine.graph.title_to_id[f"Node {i}"] = i

        # Add edges to create a specific structure
        # Node 0 is a hub (connected to all)
        for i in range(1, 5):
            edge = Edge(
                source_id=0,
                target_id=i,
                target_title=f"Node {i}",
                edge_type=EdgeType.LINKS_TO,
            )
            engine.graph.edges.append(edge)

        # Node 1 also connects to Node 2
        edge = Edge(
            source_id=1,
            target_id=2,
            target_title="Node 2",
            edge_type=EdgeType.DEPENDS_ON,
        )
        engine.graph.edges.append(edge)

        # Get stats
        stats = engine.get_graph_stats()

        # Verify stats
        assert stats["total_nodes"] == 5
        assert stats["total_edges"] == 5  # 4 from hub + 1 between nodes
        assert stats["orphan_count"] == 0  # All nodes are connected
        assert stats["average_degree"] > 0
        assert len(stats["top_hubs"]) > 0
        assert stats["top_hubs"][0]["node_id"] == 0  # Node 0 should be top hub

    def test_node_centrality_calculation(self):
        """Test node centrality calculation logic."""
        from app.services.graph_engine import GraphEngine
        from app.models.graph import Node, Edge, EdgeType

        engine = GraphEngine()

        # Create a simple graph
        for i in range(3):
            node = Node(
                id=i,
                title=f"Node {i}",
                vault_name="test",
                relative_path=f"node_{i}.md",
                note_type="note",
            )
            engine.graph.nodes[i] = node

        # Add edges: 0 -> 1, 1 -> 2, 2 -> 0 (cycle)
        edges = [
            Edge(source_id=0, target_id=1, target_title="Node 1", edge_type=EdgeType.LINKS_TO),
            Edge(source_id=1, target_id=2, target_title="Node 2", edge_type=EdgeType.DEPENDS_ON),
            Edge(source_id=2, target_id=0, target_title="Node 0", edge_type=EdgeType.RELATED_TO),
        ]
        engine.graph.edges = edges

        # Test centrality for each node
        for node_id in range(3):
            centrality = engine.get_node_centrality(node_id)
            assert centrality["node_id"] == node_id
            assert centrality["degree_centrality"] == 2  # Each has 1 in + 1 out
            assert centrality["in_degree"] == 1
            assert centrality["out_degree"] == 1
            assert centrality["normalized_centrality"] == 1.0  # 2/(3-1) = 1.0

    def test_find_hubs(self):
        """Test hub finding logic."""
        from app.services.graph_engine import GraphEngine
        from app.models.graph import Node, Edge, EdgeType

        engine = GraphEngine()

        # Create nodes with varying connectivity
        for i in range(10):
            node = Node(
                id=i,
                title=f"Node {i}",
                vault_name="test",
                relative_path=f"node_{i}.md",
                note_type="note",
            )
            engine.graph.nodes[i] = node

        # Create a power-law distribution of edges
        # Node 0: 9 edges (super hub)
        for i in range(1, 10):
            edge = Edge(
                source_id=0,
                target_id=i,
                target_title=f"Node {i}",
                edge_type=EdgeType.LINKS_TO,
            )
            engine.graph.edges.append(edge)

        # Node 1: 3 edges (minor hub)
        for i in [2, 3, 4]:
            edge = Edge(
                source_id=1,
                target_id=i,
                target_title=f"Node {i}",
                edge_type=EdgeType.DEPENDS_ON,
            )
            engine.graph.edges.append(edge)

        # Get top 3 hubs
        hubs = engine.find_hubs(limit=3)

        # Verify hub ordering
        assert len(hubs) <= 3
        assert hubs[0]["node_id"] == 0  # Node 0 should be top hub
        assert hubs[0]["degree_centrality"] == 9
        if len(hubs) > 1:
            assert hubs[1]["node_id"] == 1  # Node 1 should be second
            assert hubs[1]["degree_centrality"] >= 3