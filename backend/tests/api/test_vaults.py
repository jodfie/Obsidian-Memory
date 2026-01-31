"""Tests for vault management API endpoints."""

import json
from pathlib import Path

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
async def test_list_vaults_empty(client: AsyncClient, tmp_path, monkeypatch):
    """Test listing vaults when none exist."""
    from app.config import settings

    # Use temporary config file
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.get("/api/vaults/")
    assert response.status_code == 200
    data = response.json()
    assert "vaults" in data
    assert data["vaults"] == []
    assert data["total"] == 0
    assert data["default_vault"] is None


@pytest.mark.asyncio
async def test_list_vaults_with_data(client: AsyncClient, tmp_path, monkeypatch):
    """Test listing vaults with existing vaults."""
    from app.config import settings

    # Create vault directory
    vault_path = tmp_path / "test_vault"
    vault_path.mkdir()

    # Use temporary config file with a vault
    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "test",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": "test",
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.get("/api/vaults/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["default_vault"] == "test"
    assert len(data["vaults"]) == 1
    assert data["vaults"][0]["name"] == "test"
    assert data["vaults"][0]["is_valid"] is True


@pytest.mark.asyncio
async def test_get_vault_success(client: AsyncClient, tmp_path, monkeypatch):
    """Test getting a specific vault."""
    from app.config import settings

    # Create vault directory
    vault_path = tmp_path / "test_vault"
    vault_path.mkdir()

    # Use temporary config file
    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "test",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": None,
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.get("/api/vaults/test")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test"
    assert data["path"] == str(vault_path)
    assert data["is_valid"] is True
    assert data["file_count"] == 0  # No files yet
    assert data["memory_folder_exists"] is False


@pytest.mark.asyncio
async def test_get_vault_not_found(client: AsyncClient, tmp_path, monkeypatch):
    """Test getting a non-existent vault."""
    from app.config import settings

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.get("/api/vaults/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_vault_success(client: AsyncClient, tmp_path, monkeypatch):
    """Test creating a new vault."""
    from app.config import settings

    # Create vault directory
    vault_path = tmp_path / "new_vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    request_data = {
        "name": "new_vault",
        "path": str(vault_path),
        "memory_folder": "_claude-mem",
        "read_only": False,
        "sync_enabled": False,
        "initialize_structure": True,
    }

    response = await client.post("/api/vaults/", json=request_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "new_vault"
    assert data["is_valid"] is True

    # Verify memory folder was created
    memory_path = vault_path / "_claude-mem"
    assert memory_path.exists()
    assert (memory_path / "projects").exists()
    assert (memory_path / "global" / "patterns").exists()
    assert (memory_path / "sessions").exists()


@pytest.mark.asyncio
async def test_create_vault_invalid_path(client: AsyncClient, tmp_path, monkeypatch):
    """Test creating vault with non-existent path."""
    from app.config import settings

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    request_data = {
        "name": "invalid",
        "path": str(tmp_path / "nonexistent"),
        "initialize_structure": False,
    }

    response = await client.post("/api/vaults/", json=request_data)
    assert response.status_code == 400
    assert "validation failed" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_vault_invalid_name(client: AsyncClient, tmp_path, monkeypatch):
    """Test creating vault with invalid name."""
    from app.config import settings

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    request_data = {
        "name": "invalid name!",  # Spaces and special chars not allowed
        "path": str(vault_path),
    }

    response = await client.post("/api/vaults/", json=request_data)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_vault_duplicate(client: AsyncClient, tmp_path, monkeypatch):
    """Test creating vault with duplicate name."""
    from app.config import settings

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "existing",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": None,
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    request_data = {
        "name": "existing",  # Duplicate name
        "path": str(vault_path),
    }

    response = await client.post("/api/vaults/", json=request_data)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_vault_success(client: AsyncClient, tmp_path, monkeypatch):
    """Test updating a vault."""
    from app.config import settings

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "test",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": None,
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    update_data = {"read_only": True, "sync_enabled": True}

    response = await client.put("/api/vaults/test", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["read_only"] is True
    assert data["sync_enabled"] is True


@pytest.mark.asyncio
async def test_update_vault_not_found(client: AsyncClient, tmp_path, monkeypatch):
    """Test updating non-existent vault."""
    from app.config import settings

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    update_data = {"read_only": True}

    response = await client.put("/api/vaults/nonexistent", json=update_data)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_vault_no_changes(client: AsyncClient, tmp_path, monkeypatch):
    """Test updating vault with no changes."""
    from app.config import settings

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "test",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": None,
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    update_data = {}  # No updates

    response = await client.put("/api/vaults/test", json=update_data)
    assert response.status_code == 400
    assert "no updates" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_vault_success(client: AsyncClient, tmp_path, monkeypatch):
    """Test deleting a vault."""
    from app.config import settings

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "to_delete",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": None,
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.delete("/api/vaults/to_delete")
    assert response.status_code == 204

    # Verify vault was removed
    response = await client.get("/api/vaults/")
    data = response.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_delete_vault_not_found(client: AsyncClient, tmp_path, monkeypatch):
    """Test deleting non-existent vault."""
    from app.config import settings

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.delete("/api/vaults/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_validate_vault_success(client: AsyncClient, tmp_path, monkeypatch):
    """Test validating a vault."""
    from app.config import settings

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "test",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": None,
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.post("/api/vaults/test/validate")
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["validation_errors"] == []


@pytest.mark.asyncio
async def test_set_default_vault_success(client: AsyncClient, tmp_path, monkeypatch):
    """Test setting default vault."""
    from app.config import settings

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    config_path = tmp_path / "config.json"
    config_data = {
        "vaults": [
            {
                "name": "test",
                "path": str(vault_path),
                "memory_folder": "_claude-mem",
                "read_only": False,
                "sync_enabled": False,
            }
        ],
        "default_vault": None,
        "context_library_path": None,
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.post("/api/vaults/test/set-default")
    assert response.status_code == 204

    # Verify default was set
    response = await client.get("/api/vaults/")
    data = response.json()
    assert data["default_vault"] == "test"


@pytest.mark.asyncio
async def test_set_default_vault_not_found(client: AsyncClient, tmp_path, monkeypatch):
    """Test setting default for non-existent vault."""
    from app.config import settings

    config_path = tmp_path / "config.json"
    monkeypatch.setattr(settings, "config_file", config_path)

    response = await client.post("/api/vaults/nonexistent/set-default")
    assert response.status_code == 404
