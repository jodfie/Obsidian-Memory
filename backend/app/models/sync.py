"""Models for sync operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SyncStatus(BaseModel):
    """Sync status for a vault."""

    vault_name: str
    is_repo: bool = False
    has_remote: bool = False
    last_sync_time: datetime | None = None
    last_sync_device: str | None = None
    sync_state: str = Field(
        default="idle", description="Current sync state: idle, syncing, conflict, error"
    )
    modified_files: list[str] = Field(default_factory=list)
    untracked_files: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    pending_changes: int = 0
    device_id: str | None = None


class SyncQueueItem(BaseModel):
    """Item in the sync queue."""

    vault_name: str
    operation: str = Field(description="Operation type: commit, pull, push, sync")
    timestamp: datetime
    device_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncResult(BaseModel):
    """Result of a sync operation."""

    vault_name: str
    success: bool
    pulled: bool = False
    committed: bool = False
    pushed: bool = False
    conflicts: list[str] = Field(default_factory=list)
    updated_files: list[str] = Field(default_factory=list)
    sync_time: datetime
    device_id: str
