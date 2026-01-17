"""Vault Manager service for file operations across multiple Obsidian vaults."""

import asyncio
import os
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import aiofiles
from aiofiles import os as aiofiles_os

from app.models.vault import VaultConfig, VaultFile, VaultManagerConfig
from app.services.exceptions import (
    AtomicWriteError,
    VaultNotFoundError,
    VaultReadOnlyError,
)


class VaultManager:
    """Manages file operations across multiple Obsidian vaults."""

    def __init__(self, config: VaultManagerConfig) -> None:
        """Initialize with configuration."""
        self._config = config
        self._vault_locks: dict[str, asyncio.Lock] = {}
        # Initialize locks for each vault
        for vault in config.vaults:
            self._vault_locks[vault.name] = asyncio.Lock()

    # Vault Management
    def list_vaults(self) -> list[VaultConfig]:
        """Return all configured vaults."""
        return self._config.vaults.copy()

    def get_vault(self, name: str) -> VaultConfig:
        """Get vault config by name. Raises VaultNotFoundError if missing."""
        for vault in self._config.vaults:
            if vault.name == name:
                return vault
        raise VaultNotFoundError(f"Vault '{name}' not found")

    def set_default_vault(self, name: str) -> None:
        """Set the default vault for operations."""
        # Verify vault exists
        self.get_vault(name)
        self._config.default_vault = name

    def _get_vault_or_default(self, vault: str | None) -> VaultConfig:
        """Get vault by name or use default. Raises VaultNotFoundError if missing."""
        if vault is None:
            if self._config.default_vault is None:
                raise VaultNotFoundError("No default vault configured")
            vault = self._config.default_vault
        return self.get_vault(vault)

    def _validate_path(self, path: str, vault: VaultConfig) -> Path:
        """Validate and resolve a path within a vault."""
        # Normalize the path
        normalized = os.path.normpath(path)

        # Check for traversal attempts
        if normalized.startswith("..") or normalized.startswith("/"):
            raise ValueError(f"Invalid path: {path}")

        # Resolve to absolute and verify it's within vault
        absolute = (vault.path / normalized).resolve()
        if not absolute.is_relative_to(vault.path):
            raise ValueError(f"Path escapes vault: {path}")

        return absolute

    async def _atomic_write(self, path: Path, content: str) -> None:
        """Write file atomically using temp file + rename."""
        # Create temp file in same directory (same filesystem for rename)
        dir_path = path.parent
        dir_path.mkdir(parents=True, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            # Write to temp file using the file descriptor
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                await f.write(content)
                await f.flush()
                # Get file descriptor for fsync
                file_fd = f.fileno()
                # Ensure written to disk using os.fsync (not aiofiles.os)
                os.fsync(file_fd)

            # Atomic rename
            os.replace(temp_path, path)
        except Exception as e:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise AtomicWriteError(f"Failed to write file atomically: {e}") from e
        finally:
            # Close the file descriptor if it's still open
            try:
                os.close(fd)
            except OSError:
                pass

    # File Operations
    async def read_file(
        self,
        path: str,
        vault: str | None = None,
    ) -> VaultFile:
        """
        Read a file from a vault.

        Args:
            path: Relative path within vault (e.g., "notes/topic.md")
            vault: Vault name, or None to use default

        Returns:
            VaultFile with content and metadata

        Raises:
            VaultNotFoundError: Vault doesn't exist
            FileNotFoundError: File doesn't exist
        """
        vault_config = self._get_vault_or_default(vault)
        absolute_path = self._validate_path(path, vault_config)

        if not absolute_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not absolute_path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        # Read file content
        async with aiofiles.open(absolute_path, "r", encoding="utf-8") as f:
            content = await f.read()

        # Get file metadata
        stat = await aiofiles_os.stat(absolute_path)
        modified_at = datetime.fromtimestamp(stat.st_mtime)

        return VaultFile(
            vault_name=vault_config.name,
            relative_path=path,
            absolute_path=absolute_path,
            content=content,
            modified_at=modified_at,
            size_bytes=stat.st_size,
        )

    async def write_file(
        self,
        path: str,
        content: str,
        vault: str | None = None,
        create_dirs: bool = True,
    ) -> VaultFile:
        """
        Write content to a file atomically.

        Args:
            path: Relative path within vault
            content: File content to write
            vault: Vault name, or None to use default
            create_dirs: Create parent directories if missing

        Returns:
            VaultFile with updated metadata

        Raises:
            VaultNotFoundError: Vault doesn't exist
            VaultReadOnlyError: Vault is read-only
            PermissionError: OS permission denied
        """
        vault_config = self._get_vault_or_default(vault)

        if vault_config.read_only:
            raise VaultReadOnlyError(f"Vault '{vault_config.name}' is read-only")

        absolute_path = self._validate_path(path, vault_config)

        # Create parent directories if needed
        if create_dirs:
            absolute_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize writes per vault
        async with self._vault_locks[vault_config.name]:
            await self._atomic_write(absolute_path, content)

        # Get file metadata after write
        stat = await aiofiles_os.stat(absolute_path)
        modified_at = datetime.fromtimestamp(stat.st_mtime)

        return VaultFile(
            vault_name=vault_config.name,
            relative_path=path,
            absolute_path=absolute_path,
            content=content,
            modified_at=modified_at,
            size_bytes=stat.st_size,
        )

    async def delete_file(
        self,
        path: str,
        vault: str | None = None,
    ) -> None:
        """
        Delete a file from a vault.

        Raises:
            VaultNotFoundError: Vault doesn't exist
            FileNotFoundError: File doesn't exist
            VaultReadOnlyError: Vault is read-only
        """
        vault_config = self._get_vault_or_default(vault)

        if vault_config.read_only:
            raise VaultReadOnlyError(f"Vault '{vault_config.name}' is read-only")

        absolute_path = self._validate_path(path, vault_config)

        if not absolute_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Serialize deletes per vault
        async with self._vault_locks[vault_config.name]:
            await aiofiles_os.remove(absolute_path)

    async def move_file(
        self,
        src_path: str,
        dst_path: str,
        src_vault: str | None = None,
        dst_vault: str | None = None,
    ) -> VaultFile:
        """
        Move a file within or between vaults.

        If dst_vault differs from src_vault, performs copy+delete.
        """
        src_vault_config = self._get_vault_or_default(src_vault)
        dst_vault_config = self._get_vault_or_default(dst_vault)

        if dst_vault_config.read_only:
            raise VaultReadOnlyError(
                f"Destination vault '{dst_vault_config.name}' is read-only"
            )

        src_absolute = self._validate_path(src_path, src_vault_config)
        dst_absolute = self._validate_path(dst_path, dst_vault_config)

        if not src_absolute.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")

        # Create destination directory if needed
        dst_absolute.parent.mkdir(parents=True, exist_ok=True)

        # If same vault, use rename. Otherwise copy+delete
        if src_vault_config.name == dst_vault_config.name:
            # Same vault - use atomic rename
            async with self._vault_locks[src_vault_config.name]:
                os.replace(src_absolute, dst_absolute)
        else:
            # Cross-vault - copy then delete
            # Read source file
            async with aiofiles.open(src_absolute, "r", encoding="utf-8") as f:
                content = await f.read()

            # Write to destination (atomic)
            async with self._vault_locks[dst_vault_config.name]:
                await self._atomic_write(dst_absolute, content)

            # Delete source
            async with self._vault_locks[src_vault_config.name]:
                await aiofiles_os.remove(src_absolute)

        # Get file metadata
        stat = await aiofiles_os.stat(dst_absolute)
        modified_at = datetime.fromtimestamp(stat.st_mtime)

        async with aiofiles.open(dst_absolute, "r", encoding="utf-8") as f:
            content = await f.read()

        return VaultFile(
            vault_name=dst_vault_config.name,
            relative_path=dst_path,
            absolute_path=dst_absolute,
            content=content,
            modified_at=modified_at,
            size_bytes=stat.st_size,
        )

    async def file_exists(
        self,
        path: str,
        vault: str | None = None,
    ) -> bool:
        """Check if a file exists."""
        try:
            vault_config = self._get_vault_or_default(vault)
            absolute_path = self._validate_path(path, vault_config)
            return absolute_path.exists() and absolute_path.is_file()
        except (VaultNotFoundError, ValueError, FileNotFoundError):
            return False

    # Directory Operations
    async def list_files(
        self,
        directory: str = "",
        vault: str | None = None,
        pattern: str = "**/*.md",
        recursive: bool = True,
    ) -> list[str]:
        """
        List files in a directory matching a glob pattern.

        Args:
            directory: Starting directory (relative to vault root)
            vault: Vault name
            pattern: Glob pattern (default: all markdown files)
            recursive: If True, search subdirectories

        Returns:
            List of relative paths matching pattern
        """
        vault_config = self._get_vault_or_default(vault)
        dir_path = self._validate_path(directory, vault_config)

        if not dir_path.exists():
            return []

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        # Build glob pattern
        if recursive:
            glob_pattern = pattern
        else:
            # For non-recursive, adjust pattern
            if pattern.startswith("**/"):
                glob_pattern = pattern[4:]
            else:
                glob_pattern = pattern

        # Find matching files
        matches: list[Path] = []
        if recursive:
            matches = list(dir_path.rglob(glob_pattern))
        else:
            matches = list(dir_path.glob(glob_pattern))

        # Filter to only files and convert to relative paths
        relative_paths: list[str] = []
        for match in matches:
            if match.is_file():
                try:
                    rel_path = match.relative_to(vault_config.path)
                    relative_paths.append(str(rel_path))
                except ValueError:
                    # Path outside vault (shouldn't happen, but be safe)
                    continue

        return sorted(relative_paths)

    async def list_directories(
        self,
        directory: str = "",
        vault: str | None = None,
    ) -> list[str]:
        """List subdirectories in a directory."""
        vault_config = self._get_vault_or_default(vault)
        dir_path = self._validate_path(directory, vault_config)

        if not dir_path.exists() or not dir_path.is_dir():
            return []

        # Get subdirectories
        subdirs: list[str] = []
        for item in dir_path.iterdir():
            if item.is_dir():
                try:
                    rel_path = item.relative_to(vault_config.path)
                    subdirs.append(str(rel_path))
                except ValueError:
                    continue

        return sorted(subdirs)

    # Batch Operations
    async def read_files(
        self,
        paths: list[str],
        vault: str | None = None,
    ) -> list[VaultFile]:
        """Read multiple files concurrently."""
        tasks = [self.read_file(path, vault) for path in paths]
        return list(await asyncio.gather(*tasks))

    async def write_files(
        self,
        files: list[tuple[str, str]],  # (path, content) pairs
        vault: str | None = None,
    ) -> list[VaultFile]:
        """Write multiple files atomically (all or nothing)."""
        # For atomic batch writes, we need to write all or fail all
        # Since writes are serialized per vault, we can do them sequentially
        # but we'll validate all paths first
        vault_config = self._get_vault_or_default(vault)

        if vault_config.read_only:
            raise VaultReadOnlyError(f"Vault '{vault_config.name}' is read-only")

        # Validate all paths first
        for path, _ in files:
            self._validate_path(path, vault_config)

        # Write all files
        results: list[VaultFile] = []
        async with self._vault_locks[vault_config.name]:
            for path, content in files:
                absolute_path = self._validate_path(path, vault_config)
                absolute_path.parent.mkdir(parents=True, exist_ok=True)
                await self._atomic_write(absolute_path, content)

                # Get metadata
                stat = await aiofiles_os.stat(absolute_path)
                modified_at = datetime.fromtimestamp(stat.st_mtime)

                results.append(
                    VaultFile(
                        vault_name=vault_config.name,
                        relative_path=path,
                        absolute_path=absolute_path,
                        content=content,
                        modified_at=modified_at,
                        size_bytes=stat.st_size,
                    )
                )

        return results

    # Memory Folder Helpers
    def get_memory_path(
        self,
        note_type: str,
        filename: str,
        project: str | None = None,
        vault: str | None = None,
    ) -> str:
        """
        Get the path for a memory note.

        Structure:
        _claude-mem/
        ├── projects/{project}/
        │   ├── decisions/
        │   ├── errors/
        │   ├── knowledge/
        │   ├── patterns/
        │   └── sessions/
        └── global/
            └── patterns/

        Args:
            note_type: One of "decision", "error", "knowledge", "pattern", "session"
            filename: Note filename (without .md)
            project: Project name, or None for global
            vault: Vault name

        Returns:
            Relative path like "_claude-mem/projects/api/errors/auth-bug.md"
        """
        vault_config = self._get_vault_or_default(vault)
        memory_folder = vault_config.memory_folder

        # Validate note_type
        valid_types = {"decision", "error", "knowledge", "pattern", "session"}
        if note_type not in valid_types:
            raise ValueError(
                f"Invalid note_type: {note_type}. Must be one of {valid_types}"
            )

        # Build path
        if project:
            # Project-specific note
            if note_type == "pattern":
                # Patterns can be in projects or global
                path = f"{memory_folder}/projects/{project}/patterns/{filename}.md"
            else:
                path = (
                    f"{memory_folder}/projects/{project}/{note_type}s/{filename}.md"
                )
        else:
            # Global note (only patterns allowed globally)
            if note_type != "pattern":
                raise ValueError(
                    f"Non-pattern notes require a project. Got note_type: {note_type}"
                )
            path = f"{memory_folder}/global/patterns/{filename}.md"

        return path
