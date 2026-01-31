"""Configuration Manager service for vault configuration persistence."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

import aiofiles

from app.models.vault import VaultConfig, VaultManagerConfig
from app.services.exceptions import VaultConfigValidationError


class ConfigurationManager:
    """Manages vault configuration file operations with atomic writes."""

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to config.json file.
                        Defaults to ~/.obsidian-memory/config.json
        """
        if config_path is None:
            config_path = Path.home() / ".obsidian-memory" / "config.json"
        self.config_path = config_path
        self._lock = asyncio.Lock()

    async def load_config(self) -> VaultManagerConfig:
        """
        Load configuration from file with defaults for missing file.

        Returns:
            VaultManagerConfig loaded from file or defaults

        Raises:
            VaultConfigValidationError: If config file is corrupted
        """
        async with self._lock:
            # Return defaults if file doesn't exist
            if not self.config_path.exists():
                return VaultManagerConfig(vaults=[], default_vault=None)

            try:
                async with aiofiles.open(self.config_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)

                    # Parse and validate
                    return VaultManagerConfig.model_validate(data)
            except json.JSONDecodeError as e:
                raise VaultConfigValidationError(
                    f"Invalid JSON in config file: {e}"
                ) from e
            except Exception as e:
                raise VaultConfigValidationError(
                    f"Failed to load config: {e}"
                ) from e

    async def save_config(self, config: VaultManagerConfig) -> None:
        """
        Save configuration to file with atomic write.

        Args:
            config: Configuration to save

        Raises:
            VaultConfigValidationError: If save fails
        """
        async with self._lock:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize to JSON
            json_data = config.model_dump_json(indent=2)

            # Atomic write using temp file + rename
            dir_path = self.config_path.parent
            fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
            try:
                # Write to temp file using the file descriptor
                async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                    await f.write(json_data)
                    await f.flush()
                    # Get file descriptor for fsync
                    file_fd = f.fileno()
                    # Ensure written to disk using os.fsync
                    os.fsync(file_fd)

                # Atomic rename
                os.replace(temp_path, self.config_path)
            except Exception as e:
                # Clean up temp file on failure
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise VaultConfigValidationError(
                    f"Failed to save config: {e}"
                ) from e
            finally:
                # Close the file descriptor if it's still open
                try:
                    os.close(fd)
                except OSError:
                    pass

    async def add_vault(self, vault: VaultConfig) -> None:
        """
        Add a new vault to configuration.

        Args:
            vault: VaultConfig to add

        Raises:
            VaultConfigValidationError: If vault name already exists
        """
        config = await self.load_config()

        # Check for duplicate name
        for existing_vault in config.vaults:
            if existing_vault.name == vault.name:
                raise VaultConfigValidationError(
                    f"Vault with name '{vault.name}' already exists"
                )

        # Add vault and save
        config.vaults.append(vault)
        await self.save_config(config)

    async def remove_vault(self, name: str) -> None:
        """
        Remove a vault from configuration by name.

        Args:
            name: Vault name to remove

        Raises:
            VaultConfigValidationError: If vault doesn't exist
        """
        config = await self.load_config()

        # Find and remove vault
        vault_found = False
        updated_vaults = []
        for vault in config.vaults:
            if vault.name == name:
                vault_found = True
            else:
                updated_vaults.append(vault)

        if not vault_found:
            raise VaultConfigValidationError(f"Vault '{name}' not found")

        # Update default vault if we're removing it
        if config.default_vault == name:
            config.default_vault = None

        config.vaults = updated_vaults
        await self.save_config(config)

    async def update_vault(self, name: str, updates: dict) -> None:
        """
        Update a vault configuration with partial updates.

        Args:
            name: Vault name to update
            updates: Dictionary of field updates

        Raises:
            VaultConfigValidationError: If vault doesn't exist or update invalid
        """
        config = await self.load_config()

        # Find vault to update
        vault_found = False
        for i, vault in enumerate(config.vaults):
            if vault.name == name:
                vault_found = True
                # Create updated vault with partial updates
                vault_dict = vault.model_dump()
                vault_dict.update(updates)

                # Validate updated config
                try:
                    updated_vault = VaultConfig.model_validate(vault_dict)
                    config.vaults[i] = updated_vault
                except Exception as e:
                    raise VaultConfigValidationError(
                        f"Invalid vault update: {e}"
                    ) from e
                break

        if not vault_found:
            raise VaultConfigValidationError(f"Vault '{name}' not found")

        await self.save_config(config)
