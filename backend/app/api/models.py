"""API request/response models."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.note import ParsedNote
from app.models.search import SearchResult, SearchResults


class NoteCreateRequest(BaseModel):
    """Request model for creating a note."""

    vault_name: str = Field(..., description="Vault name")
    relative_path: str = Field(..., description="Relative path within vault")
    title: str = Field(..., description="Note title")
    content: str = Field(..., description="Markdown content")
    note_type: str = Field(default="note", description="Note type")
    project: str | None = Field(default=None, description="Project identifier")
    tags: list[str] = Field(default_factory=list, description="Tags")


class NoteUpdateRequest(BaseModel):
    """Request model for updating a note."""

    title: str | None = Field(default=None, description="Note title")
    content: str | None = Field(default=None, description="Markdown content")
    note_type: str | None = Field(default=None, description="Note type")
    project: str | None = Field(default=None, description="Project identifier")
    tags: list[str] | None = Field(default=None, description="Tags")


class NoteResponse(BaseModel):
    """Response model for a note."""

    id: int | None = Field(default=None, description="Note ID (if indexed)")
    vault_name: str = Field(..., description="Vault name")
    relative_path: str = Field(..., description="Relative path")
    permalink: str | None = Field(default=None, description="Permalink")
    title: str = Field(..., description="Note title")
    note_type: str = Field(..., description="Note type")
    project: str | None = Field(default=None, description="Project")
    content: str = Field(..., description="Note content")
    tags: list[str] = Field(default_factory=list, description="Tags")
    created_at: datetime | None = Field(default=None, description="Created at")
    updated_at: datetime | None = Field(default=None, description="Updated at")
    parsed: ParsedNote | None = Field(default=None, description="Parsed note structure")


class NoteListResponse(BaseModel):
    """Response model for note list/search."""

    results: list[SearchResult] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total matching count")
    query: str | None = Field(default=None, description="Search query")
    took_ms: float = Field(..., description="Query time in milliseconds")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    detail: str | None = Field(default=None, description="Error details")
