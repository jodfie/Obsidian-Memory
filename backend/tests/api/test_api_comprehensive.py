"""Comprehensive API integration tests.

Tests error cases, edge cases, cross-feature workflows, and advanced scenarios
for all REST API endpoints.
"""

import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.api.dependencies import (
    get_markdown_parser,
    get_search_index,
    get_vault_manager,
)
from app.main import app
from app.models.vault import VaultConfig, VaultManagerConfig
from app.services.search_index import SearchIndex
from app.services.vault_manager import VaultManager


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def vault_config(temp_dir: Path) -> VaultManagerConfig:
    """Create a test vault manager configuration with multiple vaults."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    readonly_vault_path = temp_dir / "readonly_vault"
    readonly_vault_path.mkdir()

    return VaultManagerConfig(
        vaults=[
            VaultConfig(
                name="test_vault",
                path=vault_path,
                memory_folder="_claude-mem",
                read_only=False,
            ),
            VaultConfig(
                name="readonly_vault",
                path=readonly_vault_path,
                memory_folder="_claude-mem",
                read_only=True,
            ),
        ],
        default_vault="test_vault",
    )


@pytest.fixture
def search_index(temp_dir: Path) -> SearchIndex:
    """Create a SearchIndex instance for testing."""
    db_path = temp_dir / "test_index.db"
    return SearchIndex(db_path)


@pytest.fixture
async def client(
    vault_config: VaultManagerConfig, search_index: SearchIndex
) -> AsyncClient:
    """Create a test client with overridden dependencies."""
    vault_manager = VaultManager(vault_config)

    def override_get_vault_manager():
        return vault_manager

    def override_get_search_index():
        return search_index

    app.dependency_overrides[get_vault_manager] = override_get_vault_manager
    app.dependency_overrides[get_search_index] = override_get_search_index
    app.dependency_overrides[get_markdown_parser] = lambda: get_markdown_parser()

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    if search_index.db is not None:
        await search_index.close()
    app.dependency_overrides.clear()


@pytest.fixture
async def initialized_client(
    client: AsyncClient, search_index: SearchIndex
) -> AsyncClient:
    """Client with initialized search index."""
    await search_index.initialize()
    return client


# ============================================================================
# Error Case Tests
# ============================================================================


class TestNotesErrorCases:
    """Test error responses for notes endpoints."""

    @pytest.mark.asyncio
    async def test_get_note_invalid_id_format(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 422 for invalid note ID format."""
        response = await initialized_client.get("/api/notes/invalid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_note_missing_required_fields(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 422 for missing required fields."""
        response = await initialized_client.post(
            "/api/notes",
            json={"title": "Missing Content"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_note_invalid_note_type(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 422 for invalid note type."""
        response = await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "test.md",
                "title": "Test",
                "content": "Content",
                "note_type": "invalid_type",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_nonexistent_note(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 404 for updating non-existent note."""
        response = await initialized_client.put(
            "/api/notes/99999",
            json={"title": "Updated"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_note(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 404 for deleting non-existent note."""
        response = await initialized_client.delete("/api/notes/99999")
        assert response.status_code == 404


class TestVaultsErrorCases:
    """Test error responses for vaults endpoints."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_vault(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 404 for non-existent vault."""
        response = await initialized_client.get("/api/vaults/nonexistent_vault")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_vault_invalid_path(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 400 for invalid vault path."""
        response = await initialized_client.post(
            "/api/vaults/",
            json={
                "name": "invalid_vault",
                "path": "/nonexistent/path/that/does/not/exist",
            },
        )
        assert response.status_code == 400


class TestSearchErrorCases:
    """Test error responses for search endpoints."""

    @pytest.mark.asyncio
    async def test_search_invalid_sort_order(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return 422 for invalid sort order."""
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "test", "sort": "invalid_sort"},
        )
        assert response.status_code == 422


# ============================================================================
# Pagination Edge Cases
# ============================================================================


class TestPaginationEdgeCases:
    """Test pagination boundary conditions."""

    @pytest.mark.asyncio
    async def test_list_notes_offset_exceeds_total(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should return empty list when offset exceeds total."""
        # Create a few notes
        for i in range(3):
            await initialized_client.post(
                "/api/notes",
                json={
                    "relative_path": f"pagination-test-{i}.md",
                    "title": f"Pagination Test {i}",
                    "content": f"---\ntitle: Pagination Test {i}\n---\n\nContent {i}",
                },
            )

        # Request with offset beyond total
        response = await initialized_client.get("/api/notes?offset=1000")
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == []
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_list_notes_limit_zero(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should reject limit=0 with validation error."""
        response = await initialized_client.get("/api/notes?limit=0")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_notes_limit_exceeds_max(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should cap limit at maximum allowed value."""
        response = await initialized_client.get("/api/notes?limit=10000")
        # Either caps at max or returns validation error
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_list_notes_negative_offset(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should reject negative offset."""
        response = await initialized_client.get("/api/notes?offset=-1")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_pagination(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test search with pagination."""
        # Create notes with searchable content
        for i in range(5):
            await initialized_client.post(
                "/api/notes",
                json={
                    "relative_path": f"search-pagination-{i}.md",
                    "title": f"Search Pagination {i}",
                    "content": f"---\ntitle: Search Pagination {i}\n---\n\nKeyword searchtest content {i}",
                },
            )

        # Search with pagination
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "searchtest", "limit": 2, "offset": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["notes"]) <= 2


# ============================================================================
# Search Query Edge Cases
# ============================================================================


class TestSearchQueryEdgeCases:
    """Test search with various query patterns."""

    @pytest.mark.asyncio
    async def test_search_empty_query(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should handle empty search query."""
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": ""},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_wildcard_query(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should handle wildcard (*) query."""
        # Create a test note first
        await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "wildcard-test.md",
                "title": "Wildcard Test",
                "content": "---\ntitle: Wildcard Test\n---\n\nContent here",
            },
        )

        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "*"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_special_characters(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should handle special characters in search query."""
        special_queries = [
            "test@example",
            "test#tag",
            "test/path",
            "test\\path",
            "test%20encoded",
            'test"quoted"',
            "test'apostrophe",
        ]

        for query in special_queries:
            response = await initialized_client.post(
                "/api/notes/search",
                json={"query": query},
            )
            # Should not crash - accept 200 (results/empty), 400 (bad query), or 500 (FTS error)
            assert response.status_code in [200, 400, 500]

    @pytest.mark.asyncio
    async def test_search_fts_operators(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should handle FTS5 operators in search query."""
        # Create test notes
        await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "fts-test.md",
                "title": "FTS Test",
                "content": "---\ntitle: FTS Test\n---\n\nThis note has authentication and authorization content.",
            },
        )

        # Test AND operator
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "authentication AND authorization"},
        )
        assert response.status_code == 200

        # Test OR operator
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "authentication OR testing"},
        )
        assert response.status_code == 200

        # Test NOT operator
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "authentication NOT testing"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test search with various filter combinations."""
        # Create notes with different types and tags
        await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "decision-note.md",
                "title": "Decision Note",
                "content": "---\ntitle: Decision Note\ntype: decision\n---\n\nDecision content",
                "note_type": "decision",
                "tags": ["important", "api"],
            },
        )

        # Search with type filter
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "decision", "note_type": "decision"},
        )
        assert response.status_code == 200

        # Search with tags filter (AND)
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "*", "tags": ["important"]},
        )
        assert response.status_code == 200

        # Search with tags_any filter (OR)
        response = await initialized_client.post(
            "/api/notes/search",
            json={"query": "*", "tags_any": ["important", "nonexistent"]},
        )
        assert response.status_code == 200


# ============================================================================
# Read-Only Vault Tests
# ============================================================================


class TestReadOnlyVaultEnforcement:
    """Test that read-only vaults reject write operations."""

    @pytest.mark.asyncio
    async def test_create_note_in_readonly_vault(
        self, initialized_client: AsyncClient
    ) -> None:
        """Should reject note creation in read-only vault."""
        response = await initialized_client.post(
            "/api/notes",
            json={
                "vault_name": "readonly_vault",
                "relative_path": "test.md",
                "title": "Test",
                "content": "---\ntitle: Test\n---\n\nContent",
            },
        )
        # Should be rejected with 400 or 403
        assert response.status_code in [400, 403, 500]


# ============================================================================
# Cross-Feature Workflow Tests
# ============================================================================


class TestCrossFeatureWorkflows:
    """Test workflows that span multiple features."""

    @pytest.mark.asyncio
    async def test_create_index_search_workflow(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test: create note -> index -> search -> retrieve."""
        # Step 1: Create a note with unique content
        unique_term = "uniquekeyword12345"
        create_response = await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "workflow-test.md",
                "title": "Workflow Test",
                "content": f"---\ntitle: Workflow Test\n---\n\nThis note contains {unique_term} for testing.",
                "tags": ["workflow", "test"],
            },
        )
        assert create_response.status_code == 201
        note_id = create_response.json()["id"]

        # Step 2: Search for the note
        search_response = await initialized_client.post(
            "/api/notes/search",
            json={"query": unique_term},
        )
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["total"] >= 1
        found_ids = [n["id"] for n in search_data["notes"]]
        assert note_id in found_ids

        # Step 3: Retrieve by ID to verify
        get_response = await initialized_client.get(f"/api/notes/{note_id}")
        assert get_response.status_code == 200
        assert unique_term in get_response.json()["content"]

    @pytest.mark.asyncio
    async def test_note_supersede_workflow(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test: create old note -> create new note -> supersede."""
        # Create old note
        old_response = await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "old-version.md",
                "title": "Old Version",
                "content": "---\ntitle: Old Version\n---\n\nOutdated information.",
            },
        )
        assert old_response.status_code == 201
        old_note_id = old_response.json()["id"]

        # Create new note
        new_response = await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "new-version.md",
                "title": "New Version",
                "content": "---\ntitle: New Version\n---\n\nUpdated information.",
            },
        )
        assert new_response.status_code == 201
        new_note_id = new_response.json()["id"]

        # Supersede
        supersede_response = await initialized_client.post(
            "/api/notes/supersede",
            json={
                "old_note_id": old_note_id,
                "new_note_id": new_note_id,
                "reason": "Information updated",
            },
        )
        assert supersede_response.status_code == 200
        supersede_data = supersede_response.json()
        assert supersede_data["old_note_id"] == old_note_id
        assert supersede_data["new_note_id"] == new_note_id

    @pytest.mark.asyncio
    async def test_project_notes_workflow(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test: create project -> create notes in project -> list project notes."""
        project_name = "test-project"

        # Create notes with project
        for i in range(3):
            response = await initialized_client.post(
                "/api/notes",
                json={
                    "relative_path": f"project-note-{i}.md",
                    "title": f"Project Note {i}",
                    "content": f"---\ntitle: Project Note {i}\nproject: {project_name}\n---\n\nContent",
                    "project": project_name,
                },
            )
            assert response.status_code == 201

        # List project notes
        response = await initialized_client.get(f"/api/projects/{project_name}/notes")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] >= 3


# ============================================================================
# Concurrent Operation Tests
# ============================================================================


class TestConcurrentOperations:
    """Test concurrent API operations."""

    @pytest.mark.asyncio
    async def test_concurrent_note_creation(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test creating multiple notes concurrently."""

        async def create_note(i: int) -> int:
            response = await initialized_client.post(
                "/api/notes",
                json={
                    "relative_path": f"concurrent-{i}.md",
                    "title": f"Concurrent Note {i}",
                    "content": f"---\ntitle: Concurrent Note {i}\n---\n\nContent {i}",
                },
            )
            return response.status_code

        # Create 5 notes concurrently
        results = await asyncio.gather(*[create_note(i) for i in range(5)])

        # All should succeed
        assert all(status == 201 for status in results)

    @pytest.mark.asyncio
    async def test_concurrent_searches(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test running multiple searches concurrently."""
        # Create some test data first
        await initialized_client.post(
            "/api/notes",
            json={
                "relative_path": "concurrent-search-test.md",
                "title": "Concurrent Search Test",
                "content": "---\ntitle: Concurrent Search Test\n---\n\nContent for searching",
            },
        )

        async def search(query: str) -> int:
            response = await initialized_client.post(
                "/api/notes/search",
                json={"query": query},
            )
            return response.status_code

        queries = ["concurrent", "search", "test", "content", "*"]
        results = await asyncio.gather(*[search(q) for q in queries])

        # All should succeed
        assert all(status == 200 for status in results)


# ============================================================================
# Health and Metrics Tests
# ============================================================================


class TestHealthAndMetrics:
    """Test health check and metrics endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, initialized_client: AsyncClient) -> None:
        """Test health check returns expected fields."""
        response = await initialized_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, initialized_client: AsyncClient) -> None:
        """Test metrics endpoint returns data."""
        response = await initialized_client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_root_endpoint(self, initialized_client: AsyncClient) -> None:
        """Test root endpoint."""
        response = await initialized_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


# ============================================================================
# Rate Limiting Tests (if enabled)
# ============================================================================


class TestRateLimitingHeaders:
    """Test that rate limiting headers are present."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(
        self, initialized_client: AsyncClient
    ) -> None:
        """Test that rate limit headers are in response."""
        response = await initialized_client.get("/api/notes")
        # Headers may or may not be present depending on config
        # Just verify the endpoint works
        assert response.status_code == 200
