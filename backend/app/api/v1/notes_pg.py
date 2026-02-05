"""API v1 endpoints for Postgres-backed notes CRUD operations.

This module provides FastAPI endpoints for note CRUD operations using
PostgresVaultManager and PostgresSearchIndex for database-backed storage.

All endpoints enforce user isolation through the user_id parameter.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user_id,
    get_search_index_pg,
    get_vault_manager_pg,
)
from app.db import get_db
from app.schemas.notes import Note, NoteCreate, NoteListItem, NoteUpdate
from app.schemas.search import SearchQuery, SearchResults
from app.services.exceptions import (
    DuplicatePathError,
    NoteNotFoundError,
    UnauthorizedError,
)
from app.services.search_index_pg import PostgresSearchIndex
from app.services.vault_manager_pg import PostgresVaultManager


# Response models for API documentation
class ErrorResponse(BaseModel):
    """Standard error response format."""

    detail: str = Field(..., description="Error message describing what went wrong")
    code: str | None = Field(None, description="Optional error code for client handling")

    model_config = {
        "json_schema_extra": {
            "example": {"detail": "Note not found", "code": "NOTE_NOT_FOUND"}
        }
    }


class NoteListResponse(BaseModel):
    """Paginated response for note listing."""

    notes: list[NoteListItem] = Field(..., description="List of notes")
    total: int = Field(..., description="Total number of notes matching criteria")
    limit: int = Field(..., description="Maximum number of notes returned")
    offset: int = Field(..., description="Number of notes skipped")
    has_more: bool = Field(..., description="Whether more notes are available")

    model_config = {
        "json_schema_extra": {
            "example": {
                "notes": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "path": "projects/api/design.md",
                        "title": "API Design Document",
                        "updated_at": "2024-01-15T10:30:00Z",
                        "created_at": "2024-01-10T08:00:00Z",
                    }
                ],
                "total": 42,
                "limit": 20,
                "offset": 0,
                "has_more": True,
            }
        }
    }


# Router configuration
router = APIRouter(
    prefix="/notes",
    tags=["Notes (Postgres)"],
    responses={
        401: {
            "description": "Authentication required",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Authentication required", "code": "UNAUTHORIZED"}
                }
            },
        },
        403: {
            "description": "Forbidden - User not authorized to access this resource",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authorized to access this note",
                        "code": "FORBIDDEN",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Internal server error", "code": "INTERNAL_ERROR"}
                }
            },
        },
    },
)


@router.get(
    "",
    response_model=NoteListResponse,
    summary="List notes",
    description="""
    Retrieve a paginated list of notes for the authenticated user.

    Notes are returned in order of most recently updated first.
    Use limit and offset for pagination.
    """,
    responses={
        200: {
            "description": "Successfully retrieved notes",
            "model": NoteListResponse,
        },
    },
)
async def list_notes(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of notes to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of notes to skip for pagination",
    ),
    user_id: UUID = Depends(get_current_user_id),
    vault_manager: PostgresVaultManager = Depends(get_vault_manager_pg),
) -> NoteListResponse:
    """List notes with pagination.

    Returns a paginated list of notes belonging to the authenticated user.
    Notes are ordered by updated_at descending (most recent first).
    """
    notes = await vault_manager.list_notes(user_id=user_id, limit=limit, offset=offset)
    total = await vault_manager.count_notes(user_id=user_id)

    return NoteListResponse(
        notes=notes,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(notes)) < total,
    )


@router.post(
    "",
    response_model=Note,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
    description="""
    Create a new note in the user's vault.

    The path must be unique within the user's vault. If a note already
    exists at the specified path, a 409 Conflict error is returned.
    """,
    responses={
        201: {
            "description": "Note created successfully",
            "model": Note,
        },
        409: {
            "description": "Note already exists at the specified path",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Note already exists at path: projects/design.md",
                        "code": "DUPLICATE_PATH",
                    }
                }
            },
        },
    },
)
async def create_note(
    note_data: NoteCreate,
    user_id: UUID = Depends(get_current_user_id),
    vault_manager: PostgresVaultManager = Depends(get_vault_manager_pg),
) -> Note:
    """Create a new note.

    Creates a note with the specified path, title, content, and frontmatter.
    The path must be unique within the user's vault.
    """
    try:
        note = await vault_manager.create_note(note=note_data, user_id=user_id)
        return note
    except DuplicatePathError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Note already exists at path: {e.path}",
        )


@router.get(
    "/search",
    response_model=SearchResults,
    summary="Search notes",
    description="""
    Search notes using full-text search.

    Supports:
    - Plain text queries (words are ANDed together)
    - Quoted phrases for exact matching: "exact phrase"
    - Prefix matching with * suffix: implement*

    Results are ranked by relevance and include highlighted snippets
    showing where search terms matched.
    """,
    responses={
        200: {
            "description": "Search results",
            "model": SearchResults,
        },
    },
)
async def search_notes(
    q: str = Query(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["python async", '"error handling"', "implement*"],
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of results to skip for pagination",
    ),
    user_id: UUID = Depends(get_current_user_id),
    search_index: PostgresSearchIndex = Depends(get_search_index_pg),
) -> SearchResults:
    """Search notes using full-text search.

    Uses Postgres full-text search with ts_rank for relevance ranking
    and ts_headline for snippet generation with highlighting.
    """
    search_query = SearchQuery(query=q, limit=limit, offset=offset)
    results = await search_index.search_with_query(
        search_query=search_query, user_id=user_id
    )
    return results


@router.get(
    "/{note_id}",
    response_model=Note,
    summary="Get a note by ID",
    description="Retrieve a single note by its unique identifier.",
    responses={
        200: {
            "description": "Note retrieved successfully",
            "model": Note,
        },
        404: {
            "description": "Note not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Note not found", "code": "NOTE_NOT_FOUND"}
                }
            },
        },
    },
)
async def get_note(
    note_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    vault_manager: PostgresVaultManager = Depends(get_vault_manager_pg),
) -> Note:
    """Get a specific note by ID.

    Returns the complete note including content, frontmatter, and timestamps.
    """
    try:
        note = await vault_manager.get_note_by_id(note_id=note_id, user_id=user_id)
        return note
    except NoteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this note",
        )


@router.patch(
    "/{note_id}",
    response_model=Note,
    summary="Update a note",
    description="""
    Update an existing note.

    Only provided fields will be updated. Omitted fields remain unchanged.
    If updating the path, the new path must not conflict with existing notes.
    """,
    responses={
        200: {
            "description": "Note updated successfully",
            "model": Note,
        },
        404: {
            "description": "Note not found",
            "model": ErrorResponse,
        },
        409: {
            "description": "Path conflict with existing note",
            "model": ErrorResponse,
        },
    },
)
async def update_note(
    note_id: UUID,
    note_data: NoteUpdate,
    user_id: UUID = Depends(get_current_user_id),
    vault_manager: PostgresVaultManager = Depends(get_vault_manager_pg),
) -> Note:
    """Update an existing note.

    Performs a partial update - only non-null fields in the request body
    are updated. The updated_at timestamp is automatically set.
    """
    try:
        note = await vault_manager.update_note(
            note_id=note_id, note=note_data, user_id=user_id
        )
        return note
    except NoteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this note",
        )
    except DuplicatePathError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Note already exists at path: {e.path}",
        )


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    description="Permanently delete a note. This operation cannot be undone.",
    responses={
        204: {
            "description": "Note deleted successfully",
        },
        404: {
            "description": "Note not found",
            "model": ErrorResponse,
        },
    },
)
async def delete_note(
    note_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    vault_manager: PostgresVaultManager = Depends(get_vault_manager_pg),
) -> None:
    """Delete a note.

    Permanently removes the note from the database.
    This operation cannot be undone.
    """
    try:
        await vault_manager.delete_note(note_id=note_id, user_id=user_id)
    except NoteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this note",
        )
