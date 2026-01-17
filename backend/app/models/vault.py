"""Data models for vault management."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class VaultConfig(BaseModel):
    """Configuration for a single Obsidian vault."""

    name: str = Field(..., description="Unique identifier (e.g., 'Jodys_Brain')")
    path: Path = Field(..., description="Absolute path to vault root")
    memory_folder: str = Field(
        default="_claude-mem", description="Subfolder for memory notes"
    )
    read_only: bool = Field(
        default=False, description="If true, writes are rejected"
    )
    sync_enabled: bool = Field(
        default=False, description="If true, triggers git sync after writes"
    )


class VaultFile(BaseModel):
    """Represents a file in a vault."""

    vault_name: str = Field(..., description="Which vault this belongs to")
    relative_path: str = Field(
        ..., description="Path relative to vault root (e.g., 'projects/auth.md')"
    )
    absolute_path: Path = Field(..., description="Full system path")
    content: str = Field(..., description="Raw file content")
    modified_at: datetime = Field(..., description="Last modification time")
    size_bytes: int = Field(..., description="File size")


class VaultManagerConfig(BaseModel):
    """Global vault manager configuration."""

    vaults: list[VaultConfig] = Field(..., description="List of configured vaults")
    default_vault: str | None = Field(
        default=None, description="Default vault name for operations"
    )
    context_library_path: Path | None = Field(
        default=None, description="Global contexts folder"
    )
