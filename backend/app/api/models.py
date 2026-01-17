"""API request/response models."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.note import NoteType
from app.models.search import SortOrder


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
