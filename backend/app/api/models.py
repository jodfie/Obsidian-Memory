"""API request/response models."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.models.note import NoteType
from app.models.search import SortOrder
from app.models.session import SessionEventType


class NoteCreateRequest(BaseModel):
    """Request model for creating a note."""

    vault_name: str | None = Field(default=None, description="Vault name")
    relative_path: str = Field(..., description="Relative path")
    title: str = Field(..., description="Note title")
    content: str = Field(..., description="Markdown content")
    note_type: NoteType = Field(default=NoteType.NOTE, description="Note type")
    project: str | None = Field(default=None, description="Project identifier")
    tags: list[str] = Field(default_factory=list, description="Tags")


class NoteUpdateRequest(BaseModel):
    """Request model for updating a note."""

    title: str | None = Field(default=None, description="Note title")
    content: str | None = Field(default=None, description="Markdown content")
    note_type: NoteType | None = Field(default=None, description="Note type")
    project: str | None = Field(default=None, description="Project identifier")
    tags: list[str] | None = Field(default=None, description="Tags")


class NoteResponse(BaseModel):
    """Response model for a note."""

    id: int | None = Field(default=None, description="Note ID from index")
    vault_name: str = Field(..., description="Vault name")
    relative_path: str = Field(..., description="Relative path")
    permalink: str | None = Field(default=None, description="Permalink")
    title: str = Field(..., description="Note title")
    note_type: str = Field(..., description="Note type")
    project: str | None = Field(default=None, description="Project")
    content: str = Field(..., description="Markdown content")
    tags: list[str] = Field(default_factory=list, description="Tags")
    created_at: datetime | None = Field(default=None, description="Created at")
    updated_at: datetime | None = Field(default=None, description="Updated at")


class NoteListResponse(BaseModel):
    """Response model for note list/search."""

    notes: list[NoteResponse] = Field(..., description="List of notes")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Result limit")
    offset: int = Field(..., description="Result offset")


class NoteSupersedRequest(BaseModel):
    """Request model for marking a note as superseded by another."""

    old_note_id: int = Field(..., description="ID of the note being replaced")
    new_note_id: int = Field(..., description="ID of the note that replaces it")
    reason: str | None = Field(
        default=None, description="Optional reason for superseding"
    )


class NoteSupersedResponse(BaseModel):
    """Response model for a supersede operation."""

    old_note_id: int = Field(..., description="ID of the superseded note")
    new_note_id: int = Field(..., description="ID of the new note")
    old_note_title: str = Field(..., description="Title of superseded note")
    new_note_title: str = Field(..., description="Title of new note")
    message: str = Field(..., description="Status message")


class SearchRequest(BaseModel):
    """Request model for search."""

    query: str = Field(default="", description="Search query")
    vault: str | None = Field(default=None, description="Filter by vault")
    project: str | None = Field(default=None, description="Filter by project")
    note_type: str | None = Field(default=None, description="Filter by type")
    tags: list[str] = Field(default_factory=list, description="Filter by tags (AND)")
    tags_any: list[str] = Field(
        default_factory=list, description="Filter by tags (OR)"
    )
    sort: SortOrder = Field(default=SortOrder.RELEVANCE, description="Sort order")
    limit: int = Field(default=50, ge=1, le=1000, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Result offset")


# Vault Management Models


class VaultCreateRequest(BaseModel):
    """Request model for creating/registering a vault."""

    name: str = Field(..., description="Unique vault identifier")
    path: str = Field(..., description="Absolute path to vault root")
    memory_folder: str = Field(
        default="_claude-mem", description="Subfolder for memory notes"
    )
    read_only: bool = Field(
        default=False, description="If true, writes are rejected"
    )
    sync_enabled: bool = Field(
        default=False, description="If true, triggers git sync after writes"
    )
    initialize_structure: bool = Field(
        default=True, description="If true, create memory folder structure"
    )


class VaultUpdateRequest(BaseModel):
    """Request model for updating vault configuration."""

    memory_folder: str | None = Field(default=None, description="Memory folder name")
    read_only: bool | None = Field(default=None, description="Read-only flag")
    sync_enabled: bool | None = Field(default=None, description="Sync enabled flag")


class VaultResponse(BaseModel):
    """Response model for a vault."""

    name: str = Field(..., description="Vault identifier")
    path: str = Field(..., description="Absolute path")
    memory_folder: str = Field(..., description="Memory folder name")
    read_only: bool = Field(..., description="Read-only flag")
    sync_enabled: bool = Field(..., description="Sync enabled flag")
    is_valid: bool = Field(..., description="Whether vault is valid/accessible")
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation errors if any"
    )


class VaultDetailedResponse(VaultResponse):
    """Response model for detailed vault information."""

    file_count: int | None = Field(
        default=None, description="Number of files in vault"
    )
    disk_usage_bytes: int | None = Field(
        default=None, description="Disk usage in bytes"
    )
    memory_folder_exists: bool = Field(
        ..., description="Whether memory folder exists"
    )


class VaultListResponse(BaseModel):
    """Response model for vault list."""

    vaults: list[VaultResponse] = Field(..., description="List of vaults")
    default_vault: str | None = Field(
        default=None, description="Default vault name"
    )
    total: int = Field(..., description="Total number of vaults")


class VaultStatusResponse(BaseModel):
    """Response model for vault status."""

    name: str = Field(..., description="Vault name")
    is_accessible: bool = Field(..., description="Whether vault is accessible")
    is_writable: bool = Field(..., description="Whether vault is writable")
    file_count: int | None = Field(default=None, description="Number of files")
    disk_usage_bytes: int | None = Field(default=None, description="Disk usage")
    last_modified: datetime | None = Field(default=None, description="Last modified")
    memory_folder_exists: bool = Field(..., description="Memory folder exists")
    validation_errors: list[str] = Field(default_factory=list, description="Errors")


class VaultStatusListResponse(BaseModel):
    """Response model for aggregated vault status."""

    vaults: list[VaultStatusResponse] = Field(..., description="Vault statuses")
    total: int = Field(..., description="Total number of vaults")
    healthy: int = Field(..., description="Number of healthy vaults")
    unhealthy: int = Field(..., description="Number of unhealthy vaults")


# Session Management Models


class SessionCreateRequest(BaseModel):
    """Request model for creating a session."""

    project: str | None = Field(default=None, description="Project identifier")
    session_id: str | None = Field(default=None, description="Optional session ID")


class SessionResponse(BaseModel):
    """Response model for a session."""

    session_id: str = Field(..., description="Unique session identifier")
    project: str | None = Field(default=None, description="Associated project")
    started_at: datetime = Field(..., description="Session start time")
    ended_at: datetime | None = Field(default=None, description="Session end time")
    status: str = Field(..., description="Session status (active, completed)")
    events: list[dict] = Field(default_factory=list, description="Session events")


class SessionSummaryResponse(BaseModel):
    """Response model for session summary."""

    session_id: str = Field(..., description="Session ID")
    key_learnings: list[str] = Field(
        default_factory=list, description="Key learnings from session"
    )
    decisions: list[str] = Field(
        default_factory=list, description="Decisions made during session"
    )
    errors_encountered: list[str] = Field(
        default_factory=list, description="Errors encountered"
    )
    patterns: list[str] = Field(
        default_factory=list, description="Patterns identified"
    )
