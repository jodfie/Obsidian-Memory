"""Tests for project management API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient, tmp_path, monkeypatch):
    """Test listing projects when none exist."""
    import tempfile

    from app.config import settings
    from pathlib import Path

    # Use temporary database
    db_path = tmp_path / "test_index.db"
    monkeypatch.setattr(settings, "index_db_path", db_path)

    response = await client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert "projects" in data
    assert isinstance(data["projects"], list)


@pytest.mark.asyncio
async def test_list_projects_with_data(client: AsyncClient, tmp_path, monkeypatch):
    """Test listing projects with existing notes."""
    import tempfile

    from app.config import settings
    from app.services.search_index import SearchIndex
    from app.models.search import IndexedNote
    from pathlib import Path

    # Use temporary database
    db_path = tmp_path / "test_index.db"
    monkeypatch.setattr(settings, "index_db_path", db_path)

    # Create index and add a note with a project
    index = SearchIndex(db_path)
    await index.initialize()

    indexed_note = IndexedNote(
        vault_name="test_vault",
        relative_path="test_note.md",
        title="Test Note",
        note_type="note",
        project="test-project",
        content="Test content",
        tags=[],
        file_hash="test_hash",
    )

    await index.index_note(indexed_note)
    await index.close()

    response = await client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert "projects" in data
    assert len(data["projects"]) >= 1
    assert any(p["name"] == "test-project" for p in data["projects"])


@pytest.mark.asyncio
async def test_list_project_notes(client: AsyncClient, tmp_path, monkeypatch):
    """Test listing notes for a specific project."""
    from app.config import settings
    from app.services.search_index import SearchIndex
    from app.models.search import IndexedNote

    # Use temporary database
    db_path = tmp_path / "test_index.db"
    monkeypatch.setattr(settings, "index_db_path", db_path)

    # Create index and add notes
    index = SearchIndex(db_path)
    await index.initialize()

    indexed_note = IndexedNote(
        vault_name="test_vault",
        relative_path="test_note.md",
        title="Test Note",
        note_type="note",
        project="test-project",
        content="Test content",
        tags=[],
        file_hash="test_hash",
    )

    await index.index_note(indexed_note)
    await index.close()

    response = await client.get("/api/projects/test-project/notes")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "test-project"
    assert "notes" in data
    assert len(data["notes"]) >= 1


@pytest.mark.asyncio
async def test_list_project_notes_not_found(client: AsyncClient, tmp_path, monkeypatch):
    """Test listing notes for non-existent project."""
    from app.config import settings
    from pathlib import Path

    # Use temporary database
    db_path = tmp_path / "test_index.db"
    monkeypatch.setattr(settings, "index_db_path", db_path)

    response = await client.get("/api/projects/nonexistent/notes")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "nonexistent"
    assert data["total_count"] == 0
    assert len(data["notes"]) == 0


@pytest.mark.asyncio
async def test_create_project_success(client: AsyncClient):
    """Test creating a valid project."""
    response = await client.post(
        "/api/projects", json={"project_name": "new-project"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "new-project"
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_create_project_invalid_name(client: AsyncClient):
    """Test creating a project with invalid name."""
    response = await client.post(
        "/api/projects", json={"project_name": "invalid project name!"}
    )
    assert response.status_code == 400
    assert "alphanumeric" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_project_empty_name(client: AsyncClient):
    """Test creating a project with empty name."""
    response = await client.post("/api/projects", json={"project_name": ""})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
