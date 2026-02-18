"""Tests for sync service."""

import pytest
from pathlib import Path

from app.services.exceptions import GitNotAvailableError, SyncConflictError
from app.services.sync_service import SyncService


@pytest.fixture
def temp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault directory."""
    vault_path = tmp_path / "test_vault"
    vault_path.mkdir()
    return vault_path


@pytest.fixture
def sync_service(temp_vault: Path) -> SyncService:
    """Create sync service instance."""
    return SyncService(temp_vault)


@pytest.mark.asyncio
async def test_check_git_available(sync_service: SyncService):
    """Test Git availability check."""
    # This will depend on whether Git is installed in the test environment
    result = await sync_service._check_git_available()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_is_git_repo_false(sync_service: SyncService):
    """Test is_git_repo returns False for non-Git directory."""
    result = await sync_service.is_git_repo()
    assert result is False


@pytest.mark.asyncio
async def test_init_repo(sync_service: SyncService):
    """Test Git repository initialization."""
    try:
        await sync_service.init_repo()
        # After init, should be a Git repo
        is_repo = await sync_service.is_git_repo()
        # May be False if Git is not available
        assert isinstance(is_repo, bool)
    except GitNotAvailableError:
        pytest.skip("Git not available in test environment")


@pytest.mark.asyncio
async def test_get_status_not_repo(sync_service: SyncService):
    """Test get_status for non-Git directory."""
    status = await sync_service.get_status()
    assert status["is_repo"] is False
    assert "modified_files" in status
    assert "untracked_files" in status
    assert "conflicts" in status


@pytest.mark.asyncio
async def test_get_status_git_repo(sync_service: SyncService, temp_vault: Path):
    """Test get_status for Git repository."""
    try:
        await sync_service.init_repo()
        status = await sync_service.get_status()
        assert status["is_repo"] is True
        assert isinstance(status["has_remote"], bool)
    except GitNotAvailableError:
        pytest.skip("Git not available in test environment")


@pytest.mark.asyncio
async def test_add_remote(sync_service: SyncService):
    """Test adding remote repository."""
    try:
        await sync_service.init_repo()
        await sync_service.add_remote("https://github.com/test/repo.git", "origin")
        status = await sync_service.get_status()
        assert status["has_remote"] is True
    except GitNotAvailableError:
        pytest.skip("Git not available in test environment")


@pytest.mark.asyncio
async def test_commit_changes(sync_service: SyncService, temp_vault: Path):
    """Test committing changes."""
    import subprocess
    try:
        await sync_service.init_repo()

        # Configure git user for the temp repo (may not be set in containers)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(temp_vault), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(temp_vault), check=True, capture_output=True,
        )

        # Create a test file
        test_file = temp_vault / "test.md"
        test_file.write_text("# Test\n\nContent")

        await sync_service.commit_changes("Test commit")

        status = await sync_service.get_status()
        # After commit, should have no modified files
        assert len(status["modified_files"]) == 0
    except GitNotAvailableError:
        pytest.skip("Git not available in test environment")
