# Vault Manager Specification

## Overview

The Vault Manager provides file system operations for reading and writing markdown files across multiple Obsidian vaults with atomic writes and cross-platform path handling.

## Scope

This spec covers ONLY file I/O operations. It does NOT cover:
- Parsing markdown content (see `core-markdown-parser.md`)
- Indexing or search (see `core-search-index.md`)
- Graph computation (see `graph-engine.md`)

## Data Structures

### VaultConfig

```python
from pydantic import BaseModel
from pathlib import Path

class VaultConfig(BaseModel):
    """Configuration for a single Obsidian vault."""
    name: str                    # Unique identifier (e.g., "Jodys_Brain")
    path: Path                   # Absolute path to vault root
    memory_folder: str = "_claude-mem"  # Subfolder for memory notes
    read_only: bool = False      # If true, writes are rejected
    sync_enabled: bool = False   # If true, triggers git sync after writes
```

### VaultFile

```python
class VaultFile(BaseModel):
    """Represents a file in a vault."""
    vault_name: str              # Which vault this belongs to
    relative_path: str           # Path relative to vault root (e.g., "projects/auth.md")
    absolute_path: Path          # Full system path
    content: str                 # Raw file content
    modified_at: datetime        # Last modification time
    size_bytes: int              # File size
```

### VaultManagerConfig

```python
class VaultManagerConfig(BaseModel):
    """Global vault manager configuration."""
    vaults: list[VaultConfig]
    default_vault: str | None = None  # Default vault name for operations
    context_library_path: Path | None = None  # Global contexts folder
```

## Interface

### VaultManager Class

```python
class VaultManager:
    """Manages file operations across multiple Obsidian vaults."""

    def __init__(self, config: VaultManagerConfig) -> None:
        """Initialize with configuration."""

    # Vault Management
    def list_vaults(self) -> list[VaultConfig]:
        """Return all configured vaults."""

    def get_vault(self, name: str) -> VaultConfig:
        """Get vault config by name. Raises VaultNotFoundError if missing."""

    def set_default_vault(self, name: str) -> None:
        """Set the default vault for operations."""

    # File Operations
    async def read_file(
        self,
        path: str,
        vault: str | None = None
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
            PermissionError: Vault is read-only (for some operations)
        """

    async def write_file(
        self,
        path: str,
        content: str,
        vault: str | None = None,
        create_dirs: bool = True
    ) -> VaultFile:
        """
        Write content to a file atomically.

        Uses atomic write pattern:
        1. Write to temp file in same directory
        2. Sync to disk
        3. Rename to target path

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

    async def delete_file(
        self,
        path: str,
        vault: str | None = None
    ) -> None:
        """
        Delete a file from a vault.

        Raises:
            VaultNotFoundError: Vault doesn't exist
            FileNotFoundError: File doesn't exist
            VaultReadOnlyError: Vault is read-only
        """

    async def move_file(
        self,
        src_path: str,
        dst_path: str,
        src_vault: str | None = None,
        dst_vault: str | None = None
    ) -> VaultFile:
        """
        Move a file within or between vaults.

        If dst_vault differs from src_vault, performs copy+delete.
        """

    async def file_exists(
        self,
        path: str,
        vault: str | None = None
    ) -> bool:
        """Check if a file exists."""

    # Directory Operations
    async def list_files(
        self,
        directory: str = "",
        vault: str | None = None,
        pattern: str = "**/*.md",
        recursive: bool = True
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

    async def list_directories(
        self,
        directory: str = "",
        vault: str | None = None
    ) -> list[str]:
        """List subdirectories in a directory."""

    # Batch Operations
    async def read_files(
        self,
        paths: list[str],
        vault: str | None = None
    ) -> list[VaultFile]:
        """Read multiple files concurrently."""

    async def write_files(
        self,
        files: list[tuple[str, str]],  # (path, content) pairs
        vault: str | None = None
    ) -> list[VaultFile]:
        """Write multiple files atomically (all or nothing)."""

    # Memory Folder Helpers
    def get_memory_path(
        self,
        note_type: str,
        filename: str,
        project: str | None = None,
        vault: str | None = None
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
```

## Error Handling

```python
class VaultError(Exception):
    """Base exception for vault operations."""

class VaultNotFoundError(VaultError):
    """Raised when a vault name doesn't exist in config."""

class VaultReadOnlyError(VaultError):
    """Raised when attempting to write to a read-only vault."""

class AtomicWriteError(VaultError):
    """Raised when atomic write fails (temp file, rename, etc.)."""
```

## Implementation Requirements

### Atomic Writes

All write operations MUST be atomic:

```python
import tempfile
import os

async def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically using temp file + rename."""
    # Create temp file in same directory (same filesystem for rename)
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # Ensure written to disk

        # Atomic rename
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
```

### Path Safety

All paths MUST be validated to prevent directory traversal:

```python
def _validate_path(self, path: str, vault: VaultConfig) -> Path:
    """Validate and resolve a path within a vault."""
    # Normalize the path
    normalized = os.path.normpath(path)

    # Check for traversal attempts
    if normalized.startswith('..') or normalized.startswith('/'):
        raise ValueError(f"Invalid path: {path}")

    # Resolve to absolute and verify it's within vault
    absolute = (vault.path / normalized).resolve()
    if not absolute.is_relative_to(vault.path):
        raise ValueError(f"Path escapes vault: {path}")

    return absolute
```

### Encoding

All files are read/written as UTF-8.

### Concurrency

- File reads can be concurrent (use asyncio.gather)
- File writes within a vault should be serialized (use asyncio.Lock per vault)
- Cross-vault writes can be concurrent

## Configuration File

Location: `~/.obsidian-memory/config.json`

```json
{
  "vaults": [
    {
      "name": "Jodys_Brain",
      "path": "/home/jody/Obsidian/Jodys_Brain",
      "memory_folder": "_claude-mem",
      "read_only": false,
      "sync_enabled": true
    },
    {
      "name": "Projects",
      "path": "/home/jody/Obsidian/Projects",
      "memory_folder": "_claude-mem",
      "read_only": false,
      "sync_enabled": false
    }
  ],
  "default_vault": "Jodys_Brain",
  "context_library_path": "/home/jody/.obsidian-memory/contexts"
}
```

## File Location

```
backend/
└── app/
    └── services/
        └── vault_manager.py
```

## Tests Required

```
backend/tests/
└── services/
    └── test_vault_manager.py
        ├── test_read_file_success
        ├── test_read_file_not_found
        ├── test_write_file_atomic
        ├── test_write_file_creates_dirs
        ├── test_write_file_read_only_vault
        ├── test_delete_file_success
        ├── test_move_file_same_vault
        ├── test_move_file_cross_vault
        ├── test_list_files_recursive
        ├── test_list_files_pattern
        ├── test_path_traversal_blocked
        ├── test_concurrent_reads
        ├── test_concurrent_writes_serialized
        └── test_memory_path_generation
```

## Dependencies

- `aiofiles` - Async file I/O
- `pydantic` - Data validation
- Python 3.11+ (for Path.is_relative_to)
