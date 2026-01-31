"""Tests for ConfigurationManager service."""

import json
from pathlib import Path

import pytest

from app.models.vault import VaultConfig, VaultManagerConfig
from app.services.config_manager import ConfigurationManager
from app.services.exceptions import VaultConfigValidationError


@pytest.fixture
def config_path(temp_dir: Path) -> Path:
    """Create a temporary config path."""
    return temp_dir / ".obsidian-memory" / "config.json"


@pytest.fixture
def config_manager(config_path: Path) -> ConfigurationManager:
    """Create a ConfigurationManager instance."""
    return ConfigurationManager(config_path)


@pytest.mark.asyncio
async def test_load_config_missing_file(config_manager: ConfigurationManager) -> None:
    """Test loading config when file doesn't exist returns defaults."""
    config = await config_manager.load_config()
    assert isinstance(config, VaultManagerConfig)
    assert len(config.vaults) == 0
    assert config.default_vault is None


@pytest.mark.asyncio
async def test_load_config_valid_file(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test loading a valid config file."""
    # Create config file
    config_manager.config_path.parent.mkdir(parents=True, exist_ok=True)
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

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

    config_manager.config_path.write_text(
        json.dumps(config_data, indent=2), encoding="utf-8"
    )

    # Load config
    config = await config_manager.load_config()
    assert len(config.vaults) == 1
    assert config.vaults[0].name == "test"
    assert config.default_vault == "test"


@pytest.mark.asyncio
async def test_load_config_invalid_json(
    config_manager: ConfigurationManager,
) -> None:
    """Test loading config with invalid JSON raises error."""
    config_manager.config_path.parent.mkdir(parents=True, exist_ok=True)
    config_manager.config_path.write_text("not valid json{", encoding="utf-8")

    with pytest.raises(VaultConfigValidationError, match="Invalid JSON"):
        await config_manager.load_config()


@pytest.mark.asyncio
async def test_save_config_creates_directory(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test saving config creates directory if it doesn't exist."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    config = VaultManagerConfig(
        vaults=[VaultConfig(name="test", path=vault_path)], default_vault=None
    )

    await config_manager.save_config(config)

    assert config_manager.config_path.exists()
    assert config_manager.config_path.parent.exists()


@pytest.mark.asyncio
async def test_save_config_atomic_write(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test that save_config performs atomic write."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    config = VaultManagerConfig(
        vaults=[VaultConfig(name="test", path=vault_path)], default_vault="test"
    )

    await config_manager.save_config(config)

    # Verify file was written
    assert config_manager.config_path.exists()

    # Load and verify content
    loaded_config = await config_manager.load_config()
    assert len(loaded_config.vaults) == 1
    assert loaded_config.vaults[0].name == "test"
    assert loaded_config.default_vault == "test"


@pytest.mark.asyncio
async def test_add_vault_success(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test adding a new vault."""
    vault_path = temp_dir / "new_vault"
    vault_path.mkdir()

    vault = VaultConfig(name="new_vault", path=vault_path)
    await config_manager.add_vault(vault)

    # Verify vault was added
    config = await config_manager.load_config()
    assert len(config.vaults) == 1
    assert config.vaults[0].name == "new_vault"


@pytest.mark.asyncio
async def test_add_vault_duplicate_name(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test adding vault with duplicate name raises error."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    vault1 = VaultConfig(name="duplicate", path=vault_path)
    await config_manager.add_vault(vault1)

    # Try to add another vault with same name
    vault2 = VaultConfig(name="duplicate", path=vault_path)
    with pytest.raises(VaultConfigValidationError, match="already exists"):
        await config_manager.add_vault(vault2)


@pytest.mark.asyncio
async def test_remove_vault_success(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test removing a vault."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    vault = VaultConfig(name="to_remove", path=vault_path)
    await config_manager.add_vault(vault)

    # Verify it was added
    config = await config_manager.load_config()
    assert len(config.vaults) == 1

    # Remove it
    await config_manager.remove_vault("to_remove")

    # Verify it was removed
    config = await config_manager.load_config()
    assert len(config.vaults) == 0


@pytest.mark.asyncio
async def test_remove_vault_nonexistent(
    config_manager: ConfigurationManager,
) -> None:
    """Test removing non-existent vault raises error."""
    with pytest.raises(VaultConfigValidationError, match="not found"):
        await config_manager.remove_vault("nonexistent")


@pytest.mark.asyncio
async def test_remove_vault_updates_default(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test removing default vault clears default_vault."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    vault = VaultConfig(name="default_vault", path=vault_path)
    await config_manager.add_vault(vault)

    # Set as default
    config = await config_manager.load_config()
    config.default_vault = "default_vault"
    await config_manager.save_config(config)

    # Remove it
    await config_manager.remove_vault("default_vault")

    # Verify default was cleared
    config = await config_manager.load_config()
    assert config.default_vault is None


@pytest.mark.asyncio
async def test_update_vault_success(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test updating vault configuration."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    vault = VaultConfig(name="test", path=vault_path, read_only=False)
    await config_manager.add_vault(vault)

    # Update to read-only
    await config_manager.update_vault("test", {"read_only": True})

    # Verify update
    config = await config_manager.load_config()
    assert config.vaults[0].read_only is True


@pytest.mark.asyncio
async def test_update_vault_partial_update(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test partial vault update preserves other fields."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    vault = VaultConfig(
        name="test",
        path=vault_path,
        read_only=False,
        memory_folder="_claude-mem",
        sync_enabled=False,
    )
    await config_manager.add_vault(vault)

    # Update only sync_enabled
    await config_manager.update_vault("test", {"sync_enabled": True})

    # Verify only sync_enabled changed
    config = await config_manager.load_config()
    assert config.vaults[0].sync_enabled is True
    assert config.vaults[0].read_only is False
    assert config.vaults[0].memory_folder == "_claude-mem"


@pytest.mark.asyncio
async def test_update_vault_nonexistent(
    config_manager: ConfigurationManager,
) -> None:
    """Test updating non-existent vault raises error."""
    with pytest.raises(VaultConfigValidationError, match="not found"):
        await config_manager.update_vault("nonexistent", {"read_only": True})


@pytest.mark.asyncio
async def test_update_vault_invalid_update(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test updating with invalid data raises error."""
    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    vault = VaultConfig(name="test", path=vault_path)
    await config_manager.add_vault(vault)

    # Try to update with invalid name
    with pytest.raises(VaultConfigValidationError, match="Invalid vault update"):
        await config_manager.update_vault("test", {"name": "invalid name!"})


@pytest.mark.asyncio
async def test_concurrent_access_safety(
    config_manager: ConfigurationManager, temp_dir: Path
) -> None:
    """Test that concurrent operations are safely serialized."""
    import asyncio

    vault_path = temp_dir / "vault"
    vault_path.mkdir()

    # Add initial vault
    vault = VaultConfig(name="test", path=vault_path)
    await config_manager.add_vault(vault)

    # Perform multiple concurrent updates
    async def update_sync_enabled(enabled: bool) -> None:
        await config_manager.update_vault("test", {"sync_enabled": enabled})

    tasks = [
        update_sync_enabled(i % 2 == 0) for i in range(10)
    ]  # Alternate True/False
    await asyncio.gather(*tasks)

    # Should complete without errors
    config = await config_manager.load_config()
    assert len(config.vaults) == 1
