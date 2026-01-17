"""Sync API endpoints for Git synchronization."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_vault_manager
from app.config import settings
from app.models.sync import SyncStatus
from app.services.exceptions import GitNotAvailableError, SyncConflictError
from app.services.sync_service import SyncService
from app.services.sync_state import SyncStateManager
from app.services.vault_manager import VaultManager

router = APIRouter(prefix="/api/sync", tags=["sync"])


def get_sync_state_manager() -> SyncStateManager:
    """Get sync state manager instance."""
    return SyncStateManager(settings.sync_state_file)


@router.get("/status/{vault_name}")
async def get_sync_status(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
    sync_state: SyncStateManager = Depends(get_sync_state_manager),
) -> dict[str, Any]:
    """Get sync status for a vault with cross-device tracking.

    Args:
        vault_name: Name of the vault
        vault_manager: Vault manager dependency
        sync_state: Sync state manager dependency

    Returns:
        Sync status information with cross-device metadata
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    device_id = settings.device_id
    sync_service = SyncService(vault.path, device_id=device_id)

    try:
        git_status = await sync_service.get_status()
        
        # Update sync state
        sync_state.update_sync_status(vault_name, git_status, device_id=device_id)
        
        # Get enhanced status
        enhanced_status = sync_state.get_sync_status(vault_name)
        
        if enhanced_status:
            return {
                "vault": vault_name,
                "status": enhanced_status.model_dump(),
            }
        
        # Fallback to basic status
        return {
            "vault": vault_name,
            "status": git_status,
        }
    except GitNotAvailableError:
        return {
            "vault": vault_name,
            "status": {
                "is_repo": False,
                "has_remote": False,
                "git_available": False,
                "modified_files": [],
                "untracked_files": [],
                "conflicts": [],
                "device_id": device_id,
            },
        }


@router.post("/init/{vault_name}")
async def init_sync(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> dict[str, Any]:
    """Initialize Git repository for a vault.

    Args:
        vault_name: Name of the vault

    Returns:
        Initialization result
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    sync_service = SyncService(vault.path)

    try:
        await sync_service.init_repo()
        return {
            "vault": vault_name,
            "success": True,
            "message": "Git repository initialized",
        }
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {e}") from e


@router.post("/remote/{vault_name}")
async def add_remote(
    vault_name: str,
    url: str,
    name: str = "origin",
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> dict[str, Any]:
    """Add or update remote repository for a vault.

    Args:
        vault_name: Name of the vault
        url: Remote repository URL
        name: Remote name (default: 'origin')
        vault_manager: Vault manager dependency

    Returns:
        Operation result
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    sync_service = SyncService(vault.path)

    try:
        await sync_service.add_remote(url, name)
        return {
            "vault": vault_name,
            "success": True,
            "remote": name,
            "url": url,
        }
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add remote: {e}") from e


@router.post("/commit/{vault_name}")
async def commit_changes(
    vault_name: str,
    message: str,
    author: str | None = None,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> dict[str, Any]:
    """Commit changes in a vault.

    Args:
        vault_name: Name of the vault
        message: Commit message
        author: Optional author (format: "Name <email>")
        vault_manager: Vault manager dependency

    Returns:
        Commit result
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    sync_service = SyncService(vault.path)

    try:
        await sync_service.commit_changes(message, author)
        return {
            "vault": vault_name,
            "success": True,
            "message": "Changes committed",
        }
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to commit: {e}") from e


@router.post("/pull/{vault_name}")
async def pull_changes(
    vault_name: str,
    remote: str = "origin",
    branch: str = "main",
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> dict[str, Any]:
    """Pull changes from remote repository.

    Args:
        vault_name: Name of the vault
        remote: Remote name (default: 'origin')
        branch: Branch name (default: 'main')
        vault_manager: Vault manager dependency

    Returns:
        Pull result
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    sync_service = SyncService(vault.path)

    try:
        result = await sync_service.pull(remote, branch)
        return {
            "vault": vault_name,
            "success": True,
            **result,
        }
    except SyncConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull: {e}") from e


@router.post("/push/{vault_name}")
async def push_changes(
    vault_name: str,
    remote: str = "origin",
    branch: str = "main",
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> dict[str, Any]:
    """Push changes to remote repository.

    Args:
        vault_name: Name of the vault
        remote: Remote name (default: 'origin')
        branch: Branch name (default: 'main')
        vault_manager: Vault manager dependency

    Returns:
        Push result
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    sync_service = SyncService(vault.path)

    try:
        result = await sync_service.push(remote, branch)
        return {
            "vault": vault_name,
            **result,
        }
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to push: {e}") from e


@router.post("/sync/{vault_name}")
async def sync_vault(
    vault_name: str,
    remote: str = "origin",
    branch: str = "main",
    vault_manager: VaultManager = Depends(get_vault_manager),
    sync_state: SyncStateManager = Depends(get_sync_state_manager),
) -> dict[str, Any]:
    """Perform full sync: pull, commit, push with cross-device tracking.

    Args:
        vault_name: Name of the vault
        remote: Remote name (default: 'origin')
        branch: Branch name (default: 'main')
        vault_manager: Vault manager dependency
        sync_state: Sync state manager dependency

    Returns:
        Sync result with device and timestamp information
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    device_id = settings.device_id
    sync_service = SyncService(vault.path, device_id=device_id)
    sync_state.set_sync_state(vault_name, "syncing")

    try:
        result = await sync_service.sync(remote, branch)
        
        # Update sync state with result
        status = await sync_service.get_status()
        sync_state.update_sync_status(vault_name, status, device_id=device_id)
        sync_state.set_sync_state(vault_name, "idle")
        
        return {
            "vault": vault_name,
            **result,
        }
    except SyncConflictError as e:
        sync_state.set_sync_state(vault_name, "conflict")
        raise HTTPException(status_code=409, detail=str(e)) from e
    except GitNotAvailableError as e:
        sync_state.set_sync_state(vault_name, "error")
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        sync_state.set_sync_state(vault_name, "error")
        raise HTTPException(status_code=500, detail=f"Failed to sync: {e}") from e


@router.get("/status")
async def get_all_sync_statuses(
    sync_state: SyncStateManager = Depends(get_sync_state_manager),
) -> dict[str, Any]:
    """Get sync statuses for all vaults.

    Args:
        sync_state: Sync state manager dependency

    Returns:
        Dictionary of vault sync statuses
    """
    statuses = sync_state.get_all_statuses()
    return {
        "vaults": {name: status.model_dump() for name, status in statuses.items()}
    }
