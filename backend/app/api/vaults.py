"""API endpoints for vault management."""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_config_manager, get_vault_manager
from app.api.models import (
    VaultCreateRequest,
    VaultDetailedResponse,
    VaultListResponse,
    VaultResponse,
    VaultStatusListResponse,
    VaultStatusResponse,
    VaultUpdateRequest,
)
from app.models.vault import VaultConfig
from app.services.config_manager import ConfigurationManager
from app.services.exceptions import VaultConfigValidationError, VaultNotFoundError
from app.services.vault_manager import VaultManager

router = APIRouter(prefix="/api/vaults", tags=["vaults"])


def _vault_to_response(
    vault: VaultConfig, vault_manager: VaultManager
) -> VaultResponse:
    """Convert VaultConfig to VaultResponse with validation."""
    validation_errors = vault_manager.validate_vault_config(vault)
    return VaultResponse(
        name=vault.name,
        path=str(vault.path),
        memory_folder=vault.memory_folder,
        read_only=vault.read_only,
        sync_enabled=vault.sync_enabled,
        is_valid=len(validation_errors) == 0,
        validation_errors=validation_errors,
    )


@router.get("/", response_model=VaultListResponse)
async def list_vaults(
    vault_manager: VaultManager = Depends(get_vault_manager),
    config_manager: ConfigurationManager = Depends(get_config_manager),
) -> VaultListResponse:
    """
    List all configured vaults.

    Returns:
        List of vaults with validation status
    """
    config = await config_manager.load_config()
    vaults = [
        _vault_to_response(vault, vault_manager) for vault in config.vaults
    ]

    return VaultListResponse(
        vaults=vaults, default_vault=config.default_vault, total=len(vaults)
    )


@router.get("/status", response_model=VaultStatusListResponse)
async def get_all_vaults_status(
    vault_manager: VaultManager = Depends(get_vault_manager),
    config_manager: ConfigurationManager = Depends(get_config_manager),
) -> VaultStatusListResponse:
    """
    Get aggregated status for all vaults.

    Returns:
        Status information for all configured vaults with health summary
    """
    config = await config_manager.load_config()

    vault_statuses = []
    healthy_count = 0
    unhealthy_count = 0

    for vault in config.vaults:
        try:
            vault_status = await vault_manager.get_vault_status(vault.name)
            vault_statuses.append(
                VaultStatusResponse(
                    name=vault_status.name,
                    is_accessible=vault_status.is_accessible,
                    is_writable=vault_status.is_writable,
                    file_count=vault_status.file_count,
                    disk_usage_bytes=vault_status.disk_usage_bytes,
                    last_modified=vault_status.last_modified,
                    memory_folder_exists=vault_status.memory_folder_exists,
                    validation_errors=vault_status.validation_errors,
                )
            )

            # Count as healthy if accessible and no validation errors
            if vault_status.is_accessible and not vault_status.validation_errors:
                healthy_count += 1
            else:
                unhealthy_count += 1
        except Exception:
            # If we can't get status, count as unhealthy
            unhealthy_count += 1

    return VaultStatusListResponse(
        vaults=vault_statuses,
        total=len(vault_statuses),
        healthy=healthy_count,
        unhealthy=unhealthy_count,
    )


@router.get("/{vault_name}", response_model=VaultDetailedResponse)
async def get_vault(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> VaultDetailedResponse:
    """
    Get detailed information about a specific vault.

    Args:
        vault_name: Name of the vault

    Returns:
        Detailed vault information including file counts and disk usage

    Raises:
        HTTPException: 404 if vault not found
    """
    try:
        vault = vault_manager.get_vault(vault_name)
    except VaultNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e

    # Get validation info
    validation_errors = vault_manager.validate_vault_config(vault)

    # Get file count if vault is accessible
    file_count = None
    disk_usage_bytes = None
    if len(validation_errors) == 0 and vault.path.exists():
        try:
            files = await vault_manager.list_files(vault=vault_name)
            file_count = len(files)

            # Calculate disk usage
            total_size = 0
            for file_path in files:
                try:
                    absolute_path = vault.path / file_path
                    total_size += absolute_path.stat().st_size
                except Exception:
                    pass  # Skip files we can't access
            disk_usage_bytes = total_size
        except Exception:
            pass  # If we can't list files, leave as None

    # Check if memory folder exists
    memory_path = vault.path / vault.memory_folder
    memory_folder_exists = memory_path.exists() and memory_path.is_dir()

    return VaultDetailedResponse(
        name=vault.name,
        path=str(vault.path),
        memory_folder=vault.memory_folder,
        read_only=vault.read_only,
        sync_enabled=vault.sync_enabled,
        is_valid=len(validation_errors) == 0,
        validation_errors=validation_errors,
        file_count=file_count,
        disk_usage_bytes=disk_usage_bytes,
        memory_folder_exists=memory_folder_exists,
    )


@router.get("/{vault_name}/status", response_model=VaultStatusResponse)
async def get_vault_status(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> VaultStatusResponse:
    """
    Get detailed status for a specific vault.

    Args:
        vault_name: Name of vault

    Returns:
        Vault status with accessibility, file counts, and health info

    Raises:
        HTTPException: 404 if vault not found
    """
    try:
        vault_status = await vault_manager.get_vault_status(vault_name)
    except VaultNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e

    return VaultStatusResponse(
        name=vault_status.name,
        is_accessible=vault_status.is_accessible,
        is_writable=vault_status.is_writable,
        file_count=vault_status.file_count,
        disk_usage_bytes=vault_status.disk_usage_bytes,
        last_modified=vault_status.last_modified,
        memory_folder_exists=vault_status.memory_folder_exists,
        validation_errors=vault_status.validation_errors,
    )


@router.post("/", response_model=VaultResponse, status_code=status.HTTP_201_CREATED)
async def create_vault(
    request: VaultCreateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    config_manager: ConfigurationManager = Depends(get_config_manager),
) -> VaultResponse:
    """
    Register a new vault.

    Args:
        request: Vault creation request

    Returns:
        Created vault information

    Raises:
        HTTPException: 400 if validation fails or vault already exists
    """
    # Create VaultConfig from request
    try:
        vault = VaultConfig(
            name=request.name,
            path=Path(request.path),
            memory_folder=request.memory_folder,
            read_only=request.read_only,
            sync_enabled=request.sync_enabled,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid vault configuration: {e}",
        ) from e

    # Validate vault configuration
    validation_errors = vault_manager.validate_vault_config(vault)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vault validation failed: {'; '.join(validation_errors)}",
        )

    # Add vault to configuration
    try:
        await config_manager.add_vault(vault)
    except VaultConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    # Initialize memory folder structure if requested
    if request.initialize_structure and not vault.read_only:
        memory_path = vault.path / vault.memory_folder
        memory_path.mkdir(parents=True, exist_ok=True)

        # Create standard memory folder structure
        folders = [
            "projects",
            "global/patterns",
            "sessions",
        ]
        for folder in folders:
            (memory_path / folder).mkdir(parents=True, exist_ok=True)

    return _vault_to_response(vault, vault_manager)


@router.put("/{vault_name}", response_model=VaultResponse)
async def update_vault(
    vault_name: str,
    request: VaultUpdateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    config_manager: ConfigurationManager = Depends(get_config_manager),
) -> VaultResponse:
    """
    Update vault configuration.

    Args:
        vault_name: Name of vault to update
        request: Update request with fields to change

    Returns:
        Updated vault information

    Raises:
        HTTPException: 404 if vault not found, 400 if validation fails
    """
    # Build updates dictionary (only non-None values)
    updates = {}
    if request.memory_folder is not None:
        updates["memory_folder"] = request.memory_folder
    if request.read_only is not None:
        updates["read_only"] = request.read_only
    if request.sync_enabled is not None:
        updates["sync_enabled"] = request.sync_enabled

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates provided",
        )

    try:
        await config_manager.update_vault(vault_name, updates)
    except VaultConfigValidationError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    # Reload config to get updated vault
    config = await config_manager.load_config()
    updated_vault = None
    for vault in config.vaults:
        if vault.name == vault_name:
            updated_vault = vault
            break

    if updated_vault is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vault '{vault_name}' not found after update",
        )

    # Create a new vault manager with updated config for validation
    from app.services.vault_manager import VaultManager

    temp_manager = VaultManager(config)
    return _vault_to_response(updated_vault, temp_manager)


@router.delete("/{vault_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vault(
    vault_name: str,
    config_manager: ConfigurationManager = Depends(get_config_manager),
) -> None:
    """
    Unregister a vault (does not delete files).

    Args:
        vault_name: Name of vault to remove

    Raises:
        HTTPException: 404 if vault not found
    """
    try:
        await config_manager.remove_vault(vault_name)
    except VaultConfigValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.post("/{vault_name}/validate", response_model=VaultResponse)
async def validate_vault(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> VaultResponse:
    """
    Validate vault configuration and accessibility.

    Args:
        vault_name: Name of vault to validate

    Returns:
        Vault information with validation errors

    Raises:
        HTTPException: 404 if vault not found
    """
    try:
        vault = vault_manager.get_vault(vault_name)
    except VaultNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e

    return _vault_to_response(vault, vault_manager)


@router.post("/{vault_name}/set-default", status_code=status.HTTP_204_NO_CONTENT)
async def set_default_vault(
    vault_name: str,
    vault_manager: VaultManager = Depends(get_vault_manager),
    config_manager: ConfigurationManager = Depends(get_config_manager),
) -> None:
    """
    Set a vault as the default vault.

    Args:
        vault_name: Name of vault to set as default

    Raises:
        HTTPException: 404 if vault not found
    """
    try:
        # Verify vault exists
        vault_manager.get_vault(vault_name)

        # Update config
        config = await config_manager.load_config()
        config.default_vault = vault_name
        await config_manager.save_config(config)
    except VaultNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
