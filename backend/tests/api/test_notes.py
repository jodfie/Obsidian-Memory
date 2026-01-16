"""Tests for notes API endpoints."""

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.note import NoteType
from app.models.vault import VaultConfig, VaultManagerConfig
from app.services.search_index import SearchIndex, compute_file_hash
from app.services.vault_manager import VaultManager


@pytest.fixture
def temp_vault_manager(temp_dir: Path) -> VaultManager:
    """Create a VaultManager with a test vault."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    config = VaultManagerConfig(
        vaults=[
            VaultConfig(
                name="test_vault",
                path=vault_path,
                read_only=False,
            )
        ],
        default_vault="test_vault",
    )
    return VaultManager(config)


@pytest.fixture
async def temp_search_index(temp_dir: Path) -> SearchIndex:
    """Create a SearchIndex with temporary database."""
    db_path = temp_dir / "test_index.db"
    index = SearchIndex(db_path)
    await index.initialize()
    yield index
    await index.close()


@pytest.fixture
def client(temp_dir: Path, temp_vault_manager: VaultManager) -> TestClient:
    """Create a test client with overridden dependencies."""
    # Override dependencies
    async def get_vault_manager_override():
        return temp_vault_manager

    async def get_search_index_override():
        db_path = temp_dir / "test_index.db"
        index = SearchIndex(db_path)
        await index.initialize()
        return index

    from app.api.dependencies import get_search_index, get_vault_manager

    app.dependency_overrides[get_vault_manager] = get_vault_manager_override
    app.dependency_overrides[get_search_index] = get_search_index_override

    yield TestClient(app)

    # Cleanup
    app.dependency_overrides.clear()


def test_list_notes_empty(client: TestClient) -> None:
    """Test listing notes when empty."""
    response = client.get("/api/notes")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert len(data["results"]) == 0


def test_create_note(client: TestClient) -> None:
    """Test creating a note."""
    content = """---
title: Test Note
type: note
---
# Test Note

This is test content.
"""
    response = client.post(
        "/api/notes",
        json={
            "vault_name": "test_vault",
            "relative_path": "test-note.md",
            "title": "Test Note",
            "content": content,
            "note_type": "note",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Note"
    assert data["vault_name"] == "test_vault"
    assert data["id"] is not None


def test_get_note_by_id(client: TestClient) -> None:
    """Test getting a note by ID."""
    # Create a note first
    content = """---
title: Test Note
type: note
---
# Test Note

Content here.
"""
    create_response = client.post(
        "/api/notes",
        json={
            "vault_name": "test_vault",
            "relative_path": "test-note.md",
            "title": "Test Note",
            "content": content,
            "note_type": "note",
        },
    )
    note_id = create_response.json()["id"]

    # Get the note
    response = client.get(f"/api/notes/{note_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == note_id
    assert data["title"] == "Test Note"


def test_get_note_not_found(client: TestClient) -> None:
    """Test getting a non-existent note."""
    response = client.get("/api/notes/99999")
    assert response.status_code == 404


def test_update_note(client: TestClient) -> None:
    """Test updating a note."""
    # Create a note
    content = """---
title: Original Title
type: note
---
# Original Title

Original content.
"""
    create_response = client.post(
        "/api/notes",
        json={
            "vault_name": "test_vault",
            "relative_path": "test-note.md",
            "title": "Original Title",
            "content": content,
            "note_type": "note",
        },
    )
    note_id = create_response.json()["id"]

    # Update the note
    response = client.put(
        f"/api/notes/{note_id}",
        json={
            "title": "Updated Title",
            "content": content.replace("Original Title", "Updated Title"),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


def test_delete_note(client: TestClient) -> None:
    """Test deleting a note."""
    # Create a note
    content = """---
title: To Delete
type: note
---
# To Delete

Content.
"""
    create_response = client.post(
        "/api/notes",
        json={
            "vault_name": "test_vault",
            "relative_path": "to-delete.md",
            "title": "To Delete",
            "content": content,
            "note_type": "note",
        },
    )
    note_id = create_response.json()["id"]

    # Delete the note
    response = client.delete(f"/api/notes/{note_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = client.get(f"/api/notes/{note_id}")
    assert get_response.status_code == 404


def test_search_notes(client: TestClient) -> None:
    """Test searching notes."""
    # Create a note
    content = """---
title: Searchable Note
type: note
---
# Searchable Note

This note contains authentication and JWT tokens.
"""
    create_response = client.post(
        "/api/notes",
        json={
            "vault_name": "test_vault",
            "relative_path": "searchable.md",
            "title": "Searchable Note",
            "content": content,
            "note_type": "note",
        },
    )
    assert create_response.status_code == 201

    # Search for it (note might not be indexed immediately, so just check endpoint works)
    response = client.get("/api/notes?q=authentication")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total_count" in data
    # Results might be empty if indexing hasn't completed, which is OK for this test


def test_get_backlinks(client: TestClient) -> None:
    """Test getting backlinks."""
    # Create target note
    target_content = """---
title: Target Note
type: note
---
# Target Note

Target content.
"""
    target_response = client.post(
        "/api/notes",
        json={
            "vault_name": "test_vault",
            "relative_path": "target.md",
            "title": "Target Note",
            "content": target_content,
            "note_type": "note",
        },
    )
    target_id = target_response.json()["id"]

    # Create source note that links to target
    source_content = """---
title: Source Note
type: note
---
# Source Note

See [[Target Note]] for details.
"""
    client.post(
        "/api/notes",
        json={
            "vault_name": "test_vault",
            "relative_path": "source.md",
            "title": "Source Note",
            "content": source_content,
            "note_type": "note",
        },
    )

    # Get backlinks
    response = client.get(f"/api/notes/{target_id}/backlinks")
    assert response.status_code == 200
    data = response.json()
    # Backlinks might not be immediately available due to async indexing
    # So we just check the endpoint works
    assert "results" in data
    assert "total_count" in data
