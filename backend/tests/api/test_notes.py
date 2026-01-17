"""Tests for notes API endpoints."""

from datetime import datetime
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


@pytest.fixture
def vault_config(temp_dir: Path) -> VaultManagerConfig:
    """Create a test vault manager configuration."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    return VaultManagerConfig(
        vaults=[
            VaultConfig(
                name="test_vault",
                path=vault_path,
                memory_folder="_claude-mem",
                read_only=False,
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
async def client(vault_config: VaultManagerConfig, search_index: SearchIndex) -> AsyncClient:
    """Create a test client with overridden dependencies."""
    def override_get_vault_manager():
        from app.services.vault_manager import VaultManager
        return VaultManager(vault_config)

    def override_get_search_index():
        return search_index

    app.dependency_overrides[get_vault_manager] = override_get_vault_manager
    app.dependency_overrides[get_search_index] = override_get_search_index
    app.dependency_overrides[get_markdown_parser] = lambda: get_markdown_parser()

    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_note(client: AsyncClient, search_index: SearchIndex) -> None:
    """Test creating a note."""
    await search_index.initialize()

    response = await client.post(
        "/api/notes",
        json={
            "relative_path": "test-note.md",
            "title": "Test Note",
            "content": "---\ntitle: Test Note\n---\n\n# Test Note\n\nContent here.",
            "note_type": "note",
            "tags": ["test"],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Note"
    assert data["relative_path"] == "test-note.md"
    assert data["vault_name"] == "test_vault"
    assert "test" in data["tags"]


@pytest.mark.asyncio
async def test_get_note(client: AsyncClient, search_index: SearchIndex) -> None:
    """Test getting a note by ID."""
    await search_index.initialize()

    # Create a note first
    create_response = await client.post(
        "/api/notes",
        json={
            "relative_path": "test-note.md",
            "title": "Test Note",
            "content": "---\ntitle: Test Note\n---\n\n# Test Note\n\nContent here.",
        },
    )
    assert create_response.status_code == 201
    note_id = create_response.json()["id"]

    # Get the note
    response = await client.get(f"/api/notes/{note_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == note_id
    assert data["title"] == "Test Note"


@pytest.mark.asyncio
async def test_get_note_not_found(client: AsyncClient, search_index: SearchIndex) -> None:
    """Test getting a non-existent note."""
    await search_index.initialize()

    response = await client.get("/api/notes/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_note(client: AsyncClient, search_index: SearchIndex) -> None:
    """Test updating a note."""
    await search_index.initialize()

    # Create a note first
    create_response = await client.post(
        "/api/notes",
        json={
            "relative_path": "test-note.md",
            "title": "Test Note",
            "content": "---\ntitle: Test Note\n---\n\n# Test Note\n\nContent here.",
        },
    )
    assert create_response.status_code == 201
    note_id = create_response.json()["id"]

    # Update the note
    response = await client.put(
        f"/api/notes/{note_id}",
        json={
            "title": "Updated Note",
            "tags": ["updated"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Note"
    assert "updated" in data["tags"]


@pytest.mark.asyncio
async def test_delete_note(client: AsyncClient, search_index: SearchIndex) -> None:
    """Test deleting a note."""
    await search_index.initialize()

    # Create a note first
    create_response = await client.post(
        "/api/notes",
        json={
            "relative_path": "test-note.md",
            "title": "Test Note",
            "content": "---\ntitle: Test Note\n---\n\n# Test Note\n\nContent here.",
        },
    )
    assert create_response.status_code == 201
    note_id = create_response.json()["id"]

    # Delete the note
    response = await client.delete(f"/api/notes/{note_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/api/notes/{note_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_list_notes(client: AsyncClient, search_index: SearchIndex) -> None:
    """Test listing notes."""
    await search_index.initialize()

    # Create a few notes
    for i in range(3):
        await client.post(
            "/api/notes",
            json={
                "relative_path": f"test-note-{i}.md",
                "title": f"Test Note {i}",
                "content": f"---\ntitle: Test Note {i}\n---\n\n# Test Note {i}\n\nContent {i}.",
            },
        )

    # List notes
    response = await client.get("/api/notes")
    assert response.status_code == 200
    data = response.json()
    assert len(data["notes"]) >= 3
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_search_notes(client: AsyncClient, search_index: SearchIndex) -> None:
    """Test searching notes."""
    await search_index.initialize()

    # Create a note with specific content
    await client.post(
        "/api/notes",
        json={
            "relative_path": "search-test.md",
            "title": "Search Test",
            "content": "---\ntitle: Search Test\n---\n\n# Search Test\n\nThis note contains authentication keywords.",
        },
    )

    # Search for it
    response = await client.post(
        "/api/notes/search",
        json={
            "query": "authentication",
            "limit": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any("authentication" in note["content"].lower() for note in data["notes"])
