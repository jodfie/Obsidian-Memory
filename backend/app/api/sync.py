"""Sync API endpoints for Git synchronization."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_vault_manager, get_search_index, get_markdown_parser
from app.config import settings
from app.models.search import IndexedNote
from app.models.sync import SyncStatus
from app.services.exceptions import GitNotAvailableError, SyncConflictError
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex, compute_file_hash
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
        await sync_service.init()
        return {
            "vault": vault_name,
            "status": "initialized",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize: {e}") from e


@router.post("/pull/{vault_name}")
async def pull_vault(
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
            **result,
        }
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except SyncConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull: {e}") from e


@router.post("/commit/{vault_name}")
async def commit_vault(
    vault_name: str,
    message: str | None = None,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> dict[str, Any]:
    """Commit changes to local repository.

    Args:
        vault_name: Name of the vault
        message: Commit message (auto-generated if not provided)
        vault_manager: Vault manager dependency

    Returns:
        Commit result
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    device_id = settings.device_id
    sync_service = SyncService(vault.path, device_id=device_id)

    try:
        result = await sync_service.commit(message)
        return {
            "vault": vault_name,
            **result,
        }
    except GitNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to commit: {e}") from e


@router.post("/push/{vault_name}")
async def push_vault(
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


@router.post("/reindex/{vault_name}")
async def reindex_vault(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
    parser: MarkdownParser = Depends(get_markdown_parser),
) -> dict[str, Any]:
    """Reindex all notes in a vault.

    Scans the vault directory, parses all markdown files, and updates the search index.
    This can be run while the backend is running (uses the shared SearchIndex instance).

    Args:
        vault_name: Name of the vault to reindex
        vault_manager: Vault manager dependency
        search_index: Search index dependency
        parser: Markdown parser dependency

    Returns:
        Reindex result with counts
    """
    vault = vault_manager.get_vault(vault_name)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_name} not found")

    vault_path = Path(vault.path)
    if not vault_path.exists():
        raise HTTPException(status_code=404, detail=f"Vault path does not exist: {vault.path}")

    # Scan vault for markdown files
    md_files = []
    for md_file in vault_path.rglob("*.md"):
        # Skip .obsidian folder
        if ".obsidian" in md_file.parts:
            continue
        md_files.append(md_file)

    if not md_files:
        return {
            "vault": vault_name,
            "status": "no_files",
            "added": 0,
            "updated": 0,
            "removed": 0,
            "total_files": 0,
        }

    # Parse all markdown files
    notes: list[IndexedNote] = []
    parse_errors = 0

    for md_file in md_files:
        relative_path = md_file.relative_to(vault_path)
        
        try:
            content = md_file.read_text(encoding="utf-8")
            file_hash = compute_file_hash(content)
            
            try:
                parsed = parser.parse(content)
            except Exception as e:
                # Log parse error for debugging
                print(f"Parse error for {relative_path}: {e}")
                # Create minimal note on parse error
                stat = md_file.stat()
                created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
                updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                
                note = IndexedNote(
                    note_id=0,
                    vault_name=vault_name,
                    relative_path=str(relative_path),
                    permalink=str(relative_path),
                    title=md_file.stem,
                    note_type="note",
                    project=None,
                    content=content,
                    tags=[],
                    wikilinks=[],
                    relations=[],
                    observations=[],
                    created_at=created_at,
                    updated_at=updated_at,
                    file_hash=file_hash,
                )
                notes.append(note)
                parse_errors += 1
                continue
            
            # Create IndexedNote from parsed content
            stat = md_file.stat()
            created_at = parsed.frontmatter.created or datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
            updated_at = parsed.frontmatter.updated or datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            
            permalink = parsed.frontmatter.permalink or str(relative_path)
            
            note = IndexedNote(
                note_id=0,
                vault_name=vault_name,
                relative_path=str(relative_path),
                permalink=permalink,
                title=parsed.frontmatter.title,
                note_type=parsed.frontmatter.type.value if hasattr(parsed.frontmatter.type, 'value') else str(parsed.frontmatter.type),
                project=parsed.frontmatter.project,
                content=content,
                tags=parsed.frontmatter.tags,
                wikilinks=parsed.wikilinks,
                relations=parsed.relations,
                observations=parsed.observations,
                created_at=created_at,
                updated_at=updated_at,
                file_hash=file_hash,
            )
            notes.append(note)
            
        except Exception as e:
            print(f"File error for {relative_path}: {e}")
            parse_errors += 1
            continue

    if not notes:
        return {
            "vault": vault_name,
            "status": "parse_failed",
            "added": 0,
            "updated": 0,
            "removed": 0,
            "total_files": len(md_files),
            "parse_errors": parse_errors,
        }

    # Index notes using the shared SearchIndex
    try:
        # Ensure index is initialized
        if not search_index.db:
            await search_index.initialize()
            
        added, updated, removed = await search_index.index_vault(
            vault_name=vault_name,
            notes=notes,
        )
        
        return {
            "vault": vault_name,
            "status": "success",
            "added": added,
            "updated": updated,
            "removed": removed,
            "total_files": len(md_files),
            "parse_errors": parse_errors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to index: {e}") from e
