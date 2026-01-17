"""Tests for sync state management."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.models.sync import SyncStatus
from app.services.sync_state import SyncStateManager


@pytest.fixture
def temp_state_file():
    """Create a temporary state file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def sync_state(temp_state_file):
    """Create a SyncStateManager instance."""
    return SyncStateManager(temp_state_file)


def test_get_sync_status_not_found(sync_state):
    """Test getting status for non-existent vault."""
    status = sync_state.get_sync_status("nonexistent")
    assert status is None


def test_update_sync_status(sync_state):
    """Test updating sync status."""
    status_data = {
        "is_repo": True,
        "has_remote": True,
        "modified_files": ["file1.md", "file2.md"],
        "untracked_files": ["file3.md"],
        "conflicts": [],
    }
    
    sync_state.update_sync_status("test_vault", status_data, device_id="device-1")
    
    status = sync_state.get_sync_status("test_vault")
    assert status is not None
    assert status.vault_name == "test_vault"
    assert status.is_repo is True
    assert status.has_remote is True
    assert status.modified_files == ["file1.md", "file2.md"]
    assert status.untracked_files == ["file3.md"]
    assert status.device_id == "device-1"
    assert status.last_sync_device == "device-1"
    assert status.last_sync_time is not None
    assert status.pending_changes == 3  # 2 modified + 1 untracked


def test_set_sync_state(sync_state):
    """Test setting sync state."""
    status_data = {"is_repo": True, "has_remote": False}
    sync_state.update_sync_status("test_vault", status_data)
    
    sync_state.set_sync_state("test_vault", "syncing")
    
    status = sync_state.get_sync_status("test_vault")
    assert status is not None
    assert status.sync_state == "syncing"


def test_get_all_statuses(sync_state):
    """Test getting all sync statuses."""
    sync_state.update_sync_status("vault1", {"is_repo": True}, device_id="device-1")
    sync_state.update_sync_status("vault2", {"is_repo": False}, device_id="device-2")
    
    all_statuses = sync_state.get_all_statuses()
    
    assert len(all_statuses) == 2
    assert "vault1" in all_statuses
    assert "vault2" in all_statuses
    assert all_statuses["vault1"].device_id == "device-1"
    assert all_statuses["vault2"].device_id == "device-2"


def test_persist_state(sync_state, temp_state_file):
    """Test that state persists across instances."""
    status_data = {"is_repo": True, "has_remote": True}
    sync_state.update_sync_status("test_vault", status_data, device_id="device-1")
    
    # Create new instance
    new_sync_state = SyncStateManager(temp_state_file)
    status = new_sync_state.get_sync_status("test_vault")
    
    assert status is not None
    assert status.is_repo is True
    assert status.has_remote is True
    assert status.device_id == "device-1"
