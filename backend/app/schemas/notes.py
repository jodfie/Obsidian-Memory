"""Pydantic schemas for note CRUD operations.

These schemas are used for API request/response validation and serialization
when working with the Postgres-backed vault manager.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoteBase(BaseModel):
    """Base schema with common note fields."""

    path: str = Field(
        ...,
        description="Vault-style path (e.g., 'projects/my-project/design.md')",
        min_length=1,
        max_length=1000,
    )
    title: str = Field(
        ...,
        description="Note title",
        min_length=1,
        max_length=500,
    )
    content: str = Field(
        default="",
        description="Markdown content body (without frontmatter)",
    )
    frontmatter: dict[str, Any] = Field(
        default_factory=dict,
        description="YAML frontmatter metadata as JSON",
    )


class NoteCreate(NoteBase):
    """Schema for creating a new note.

    Used in POST /notes endpoint.
    """

    pass


class NoteUpdate(BaseModel):
    """Schema for updating an existing note.

    All fields are optional - only provided fields will be updated.
    Used in PATCH /notes/{note_id} endpoint.
    """

    path: str | None = Field(
        default=None,
        description="New vault-style path (for moving/renaming)",
        min_length=1,
        max_length=1000,
    )
    title: str | None = Field(
        default=None,
        description="New note title",
        min_length=1,
        max_length=500,
    )
    content: str | None = Field(
        default=None,
        description="New markdown content body",
    )
    frontmatter: dict[str, Any] | None = Field(
        default=None,
        description="New frontmatter metadata (replaces existing)",
    )


class Note(NoteBase):
    """Full note schema with all fields.

    Returned from GET /notes/{note_id} and other endpoints that return complete notes.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique note identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")
    user_id: UUID | None = Field(
        default=None,
        description="Owner user ID (for multi-tenancy)",
    )


class NoteListItem(BaseModel):
    """Lightweight note schema for list views.

    Contains only essential fields for displaying notes in lists.
    Used in GET /notes endpoint for efficiency.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique note identifier")
    path: str = Field(..., description="Vault-style path")
    title: str = Field(..., description="Note title")
    updated_at: datetime = Field(..., description="Last modification timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
