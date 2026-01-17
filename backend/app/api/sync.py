"""Sync API endpoints for Git synchronization."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_vault_manager
from app.services.exceptions import GitNotAvailableError, SyncConflictError
from app.services.sync_service import SyncService
from app.services.vault_manager import VaultManager

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status/{vault_name}")
async def get_sync_status(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> dict[str, Any]:
    """Get sync status for a vault.

    Args:
        vault_name: Name of the vault
        vault_name: Name of the vault

    Returns:
        Sync status information
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    sync_service = SyncService(vault.path)

    try:
        status = await sync_service.get_status()
        return {
            "vault": vault_name,
            "status": status,
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
) -> dict[str, Any]:
    """Perform full sync: pull, commit, push.

    Args:
        vault_name: Name of the vault
        remote: Remote name (default: 'origin')
        branch: Branch name (default: 'main')
        vault_manager: Vault manager dependency

    Returns:
        Sync result
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    sync_service = SyncService(vault.path)

    try:
        result = await sync_service.sync(remote, branch)
        return {
            "vault": vault_name,
            **result,
        }
    except SyncConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync: {e}") from e
