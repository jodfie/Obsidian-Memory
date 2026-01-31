"""API v1 endpoints for notes CRUD operations with comprehensive OpenAPI documentation."""

import hashlib
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_markdown_parser,
    get_search_index,
    get_vault_manager,
)
from app.api.models import (
    NoteCreateRequest,
    NoteResponse,
    NoteSupersedRequest,
    NoteSupersedResponse,
    NoteUpdateRequest,
    SearchRequest,
)
from app.models.note import ParsedNote
from app.models.search import IndexedNote, SearchQuery
from app.services.exceptions import VaultNotFoundError
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex, compute_file_hash
from app.services.vault_manager import VaultManager
from app.utils.cache import get_cache

# Enhanced response models with examples
class ErrorResponse(BaseModel):
    """Standard error response format."""
    detail: str = Field(..., description="Error message describing what went wrong")
    code: Optional[str] = Field(None, description="Optional error code for client handling")

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Note not found with ID: 123",
                "code": "NOTE_NOT_FOUND"
            }
        }


class NoteListResponseV1(BaseModel):
    """Response for note listing with pagination metadata."""
    notes: List[NoteResponse] = Field(..., description="List of notes matching the criteria")
    total: int = Field(..., description="Total number of notes matching the criteria")
    limit: int = Field(..., description="Maximum number of notes returned")
    offset: int = Field(..., description="Number of notes skipped")
    has_more: bool = Field(..., description="Whether more notes are available")

    class Config:
        json_schema_extra = {
            "example": {
                "notes": [
                    {
                        "id": 1,
                        "vault_name": "main",
                        "relative_path": "projects/api/authentication.md",
                        "title": "Authentication System Design",
                        "note_type": "knowledge",
                        "project": "api-v2",
                        "content": "# Authentication System\n\nImplementation details...",
                        "tags": ["auth", "security", "oauth"],
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-16T14:45:00Z"
                    }
                ],
                "total": 150,
                "limit": 50,
                "offset": 0,
                "has_more": True
            }
        }


router = APIRouter(
    prefix="/notes",
    tags=["Notes"],
    responses={
        401: {
            "description": "Authentication required",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Cloudflare Access JWT token required"}
                }
            }
        },
        403: {
            "description": "Forbidden - Invalid authentication",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid authentication token"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Internal server error occurred"}
                }
            }
        }
    }
)


async def _ensure_search_index_initialized(
    search_index: SearchIndex,
) -> None:
    """Ensure search index is initialized."""
    if not search_index.db:
        await search_index.initialize()


@router.get(
    "",
    response_model=NoteListResponseV1,
    summary="List notes",
    description="Retrieve a paginated list of notes with optional filtering by vault, project, and other criteria.",
    responses={
        200: {
            "description": "Successfully retrieved notes",
            "model": NoteListResponseV1,
        },
        400: {
            "description": "Invalid request parameters",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid limit: must be between 1 and 500"}
                }
            }
        }
    }
)
async def list_notes(
    vault: Optional[str] = Query(None, description="Filter by vault name", example="main"),
    project: Optional[str] = Query(None, description="Filter by project", example="api-v2"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of notes to return"),
    offset: int = Query(0, ge=0, description="Number of notes to skip for pagination"),
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteListResponseV1:
    """List notes with optional filtering and pagination.

    This endpoint supports:
    - Filtering by vault name
    - Filtering by project
    - Pagination with limit and offset
    - Automatic search index initialization

    Notes are returned in order of most recently updated first by default.
    """
    # Enforce maximum limit to prevent performance issues
    limit = min(limit, 500)

    # Validate offset
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid offset: must be >= 0"
        )

    await _ensure_search_index_initialized(search_index)

    # Build search query
    query = SearchQuery(
        query="*",  # Match all
        vault=vault,
        project=project,
        limit=limit,
        offset=offset,
    )

    results = await search_index.search(query)

    # Convert to response models
    notes: List[NoteResponse] = []
    for result in results.results:
        # Get full note content from vault
        try:
            vault_file = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )
            content = vault_file.content
        except Exception:
            content = ""

        notes.append(
            NoteResponse(
                id=result.note_id,
                vault_name=result.vault_name,
                relative_path=result.relative_path,
                permalink=result.permalink,
                title=result.title,
                note_type=result.note_type,
                project=result.project,
                content=content,
                tags=result.tags,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        )

    has_more = (offset + len(notes)) < results.total_count

    return NoteListResponseV1(
        notes=notes,
        total=results.total_count,
        limit=limit,
        offset=offset,
        has_more=has_more
    )


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
    description="Create a new note in the specified vault.",
    responses={
        201: {
            "description": "Note created successfully",
            "model": NoteResponse,
        },
        400: {
            "description": "Invalid request body",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid path: contains illegal characters"}
                }
            }
        },
        404: {
            "description": "Vault not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Vault not found: unknown"}
                }
            }
        },
        409: {
            "description": "Note already exists",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Note already exists at path: projects/existing.md"}
                }
            }
        }
    }
)
async def create_note(
    request: NoteCreateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteResponse:
    """Create a new note.

    This endpoint:
    - Creates the note file in the vault
    - Parses markdown metadata
    - Indexes the note for search
    - Returns the created note with generated ID

    The note will be created with proper frontmatter metadata.
    """
    await _ensure_search_index_initialized(search_index)

    # Validate vault exists
    if request.vault_name:
        try:
            vault = vault_manager.get_vault(request.vault_name)
        except VaultNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vault not found: {request.vault_name}",
            )
    else:
        vaults = list(vault_manager.vaults.values())
        if not vaults:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No vaults configured",
            )
        vault = vaults[0]

    # Check if note already exists
    try:
        existing = await vault_manager.read_file(
            request.relative_path, vault=vault.name
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Note already exists at path: {request.relative_path}",
            )
    except FileNotFoundError:
        pass  # Expected - note doesn't exist yet

    # Create note with metadata
    metadata = {
        "title": request.title,
        "note_type": request.note_type or "note",
        "project": request.project,
        "tags": request.tags or [],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }

    # Format content with frontmatter
    content_lines = ["---"]
    for key, value in metadata.items():
        if value is not None:
            if isinstance(value, list):
                content_lines.append(f"{key}: {', '.join(value)}")
            else:
                content_lines.append(f"{key}: {value}")
    content_lines.append("---")
    content_lines.append("")
    content_lines.append(request.content)
    full_content = "\n".join(content_lines)

    # Write file to vault
    vault_file = await vault_manager.write_file(
        request.relative_path, full_content, vault=vault.name
    )

    # Parse the note
    parsed = await markdown_parser.parse(vault_file.absolute_path)

    # Compute permalink
    file_hash = compute_file_hash(vault_file.absolute_path)
    permalink = f"{vault.name}/{request.relative_path}#{file_hash[:8]}"

    # Index the note
    indexed_note = IndexedNote(
        note_id=hash(vault_file.absolute_path) % (2**31),  # Generate stable ID
        vault_name=vault.name,
        relative_path=request.relative_path,
        absolute_path=str(vault_file.absolute_path),
        permalink=permalink,
        title=request.title,
        content=request.content,
        note_type=request.note_type or "note",
        project=request.project,
        tags=request.tags or [],
        frontmatter=parsed.frontmatter,
        file_hash=file_hash,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await search_index.index_note(indexed_note)

    return NoteResponse(
        id=indexed_note.note_id,
        vault_name=vault.name,
        relative_path=request.relative_path,
        permalink=permalink,
        title=request.title,
        note_type=request.note_type or "note",
        project=request.project,
        content=request.content,
        tags=request.tags or [],
        created_at=indexed_note.created_at,
        updated_at=indexed_note.updated_at,
    )


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get a note by ID",
    description="Retrieve a single note by its unique identifier.",
    responses={
        200: {
            "description": "Note retrieved successfully",
            "model": NoteResponse,
        },
        404: {
            "description": "Note not found",
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {"detail": "Note not found with ID: 123"}
                }
            }
        }
    }
)
async def get_note(
    note_id: int = Field(..., description="Unique identifier of the note"),
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> NoteResponse:
    """Get a specific note by ID.

    Returns the complete note including:
    - Metadata (title, type, tags, etc.)
    - Full content
    - Timestamps
    - Vault information
    """
    await _ensure_search_index_initialized(search_index)

    # Get note from index
    note = await search_index.get_note_by_id(note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found with ID: {note_id}",
        )

    # Get full content from vault
    try:
        vault_file = await vault_manager.read_file(
            note.relative_path, vault=note.vault_name
        )
        content = vault_file.content
    except FileNotFoundError:
        content = ""

    return NoteResponse(
        id=note.note_id,
        vault_name=note.vault_name,
        relative_path=note.relative_path,
        permalink=note.permalink,
        title=note.title,
        note_type=note.note_type,
        project=note.project,
        content=content,
        tags=note.tags,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update a note",
    description="Update an existing note's content and metadata.",
    responses={
        200: {
            "description": "Note updated successfully",
            "model": NoteResponse,
        },
        404: {
            "description": "Note not found",
            "model": ErrorResponse,
        },
        409: {
            "description": "Conflict - Note was modified by another process",
            "model": ErrorResponse,
        }
    }
)
async def update_note(
    note_id: int,
    request: NoteUpdateRequest,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
) -> NoteResponse:
    """Update an existing note.

    This endpoint:
    - Updates the note content and/or metadata
    - Re-indexes the note for search
    - Preserves the note ID and creation date
    - Updates the modification timestamp
    """
    await _ensure_search_index_initialized(search_index)

    # Get existing note
    existing_note = await search_index.get_note_by_id(note_id)
    if not existing_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found with ID: {note_id}",
        )

    # Update metadata
    metadata = {
        "title": request.title or existing_note.title,
        "note_type": request.note_type or existing_note.note_type,
        "project": request.project if request.project is not None else existing_note.project,
        "tags": request.tags if request.tags is not None else existing_note.tags,
        "created_at": existing_note.created_at.isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }

    # Get content
    if request.content is not None:
        content = request.content
    else:
        vault_file = await vault_manager.read_file(
            existing_note.relative_path, vault=existing_note.vault_name
        )
        parsed = await markdown_parser.parse(vault_file.absolute_path)
        content = parsed.content

    # Format content with frontmatter
    content_lines = ["---"]
    for key, value in metadata.items():
        if value is not None:
            if isinstance(value, list):
                content_lines.append(f"{key}: {', '.join(value)}")
            else:
                content_lines.append(f"{key}: {value}")
    content_lines.append("---")
    content_lines.append("")
    content_lines.append(content)
    full_content = "\n".join(content_lines)

    # Write updated file
    vault_file = await vault_manager.write_file(
        existing_note.relative_path, full_content, vault=existing_note.vault_name
    )

    # Re-index the note
    file_hash = compute_file_hash(vault_file.absolute_path)
    updated_note = IndexedNote(
        note_id=existing_note.note_id,
        vault_name=existing_note.vault_name,
        relative_path=existing_note.relative_path,
        absolute_path=str(vault_file.absolute_path),
        permalink=existing_note.permalink,
        title=metadata["title"],
        content=content,
        note_type=metadata["note_type"],
        project=metadata.get("project"),
        tags=metadata.get("tags", []),
        frontmatter=metadata,
        file_hash=file_hash,
        created_at=existing_note.created_at,
        updated_at=datetime.utcnow(),
    )
    await search_index.index_note(updated_note)

    return NoteResponse(
        id=updated_note.note_id,
        vault_name=updated_note.vault_name,
        relative_path=updated_note.relative_path,
        permalink=updated_note.permalink,
        title=updated_note.title,
        note_type=updated_note.note_type,
        project=updated_note.project,
        content=content,
        tags=updated_note.tags,
        created_at=updated_note.created_at,
        updated_at=updated_note.updated_at,
    )


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    description="Permanently delete a note from the vault and search index.",
    responses={
        204: {
            "description": "Note deleted successfully",
        },
        404: {
            "description": "Note not found",
            "model": ErrorResponse,
        }
    }
)
async def delete_note(
    note_id: int,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> None:
    """Delete a note.

    This endpoint:
    - Removes the note from the search index
    - Deletes the file from the vault
    - This operation cannot be undone
    """
    await _ensure_search_index_initialized(search_index)

    # Get note from index
    note = await search_index.get_note_by_id(note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found with ID: {note_id}",
        )

    # Delete from vault
    try:
        await vault_manager.delete_file(
            note.relative_path, vault=note.vault_name
        )
    except FileNotFoundError:
        pass  # Already deleted

    # Remove from index
    await search_index.delete_note(note_id)


@router.post(
    "/search",
    response_model=NoteListResponseV1,
    summary="Search notes",
    description="Search notes using full-text search with optional filters.",
    responses={
        200: {
            "description": "Search results",
            "model": NoteListResponseV1,
        },
        400: {
            "description": "Invalid search query",
            "model": ErrorResponse,
        }
    }
)
async def search_notes(
    request: SearchRequest,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
) -> NoteListResponseV1:
    """Search notes with advanced filtering.

    Features:
    - Full-text search using FTS5
    - Filter by vault, project, type, tags
    - Configurable sorting
    - Pagination support
    - Snippet extraction for matches

    Search syntax supports:
    - Simple terms: `api`
    - Phrases: `"authentication system"`
    - Boolean operators: `auth AND security`
    - Exclusions: `api NOT deprecated`
    """
    await _ensure_search_index_initialized(search_index)

    # Validate and enforce limits
    limit = min(request.limit or 50, 500)
    offset = max(request.offset or 0, 0)

    # Build search query
    query = SearchQuery(
        query=request.query,
        vault=request.vault,
        project=request.project,
        note_type=request.note_type,
        tags=request.tags,
        tags_any=request.tags_any,
        sort=request.sort or "relevance",
        limit=limit,
        offset=offset,
    )

    results = await search_index.search(query)

    # Convert to response models
    notes: List[NoteResponse] = []
    for result in results.results:
        # Get full note content from vault
        try:
            vault_file = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )
            content = vault_file.content
        except Exception:
            content = ""

        notes.append(
            NoteResponse(
                id=result.note_id,
                vault_name=result.vault_name,
                relative_path=result.relative_path,
                permalink=result.permalink,
                title=result.title,
                note_type=result.note_type,
                project=result.project,
                content=content,
                tags=result.tags,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        )

    has_more = (offset + len(notes)) < results.total_count

    return NoteListResponseV1(
        notes=notes,
        total=results.total_count,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.post(
    "/supersede",
    response_model=NoteSupersedResponse,
    summary="Supersede a note",
    description="Mark a note as superseded by another note, creating a bi-directional relationship.",
    responses={
        200: {
            "description": "Note superseded successfully",
            "model": NoteSupersedResponse,
        },
        404: {
            "description": "Note not found",
            "model": ErrorResponse,
        },
        400: {
            "description": "Invalid request",
            "model": ErrorResponse,
        }
    }
)
async def supersede_note(
    request: NoteSupersedRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteSupersedResponse:
    """Mark a note as superseded by another note.

    This creates a bi-directional supersedes relationship:
    - The old note gets a `superseded_by` field pointing to the new note
    - The new note gets a `supersedes` field pointing to the old note

    This is useful for:
    - Tracking document revisions
    - Maintaining knowledge history
    - Deprecating outdated information
    """
    await _ensure_search_index_initialized(search_index)

    # Get both notes
    old_note = await search_index.get_note_by_id(request.old_note_id)
    if not old_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Old note not found with ID: {request.old_note_id}",
        )

    new_note = await search_index.get_note_by_id(request.new_note_id)
    if not new_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"New note not found with ID: {request.new_note_id}",
        )

    if request.old_note_id == request.new_note_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot supersede a note with itself",
        )

    # Update old note metadata
    old_file = await vault_manager.read_file(
        old_note.relative_path, vault=old_note.vault_name
    )
    old_parsed = await markdown_parser.parse(old_file.absolute_path)
    old_metadata = old_parsed.frontmatter.copy()
    old_metadata["superseded_by"] = request.new_note_id
    if request.reason:
        old_metadata["superseded_reason"] = request.reason
    old_metadata["updated_at"] = datetime.utcnow().isoformat() + "Z"

    # Format old note content
    old_content_lines = ["---"]
    for key, value in old_metadata.items():
        if value is not None:
            if isinstance(value, list):
                old_content_lines.append(f"{key}: {', '.join(map(str, value))}")
            else:
                old_content_lines.append(f"{key}: {value}")
    old_content_lines.append("---")
    old_content_lines.append("")
    old_content_lines.append(old_parsed.content)
    old_full_content = "\n".join(old_content_lines)

    # Update new note metadata
    new_file = await vault_manager.read_file(
        new_note.relative_path, vault=new_note.vault_name
    )
    new_parsed = await markdown_parser.parse(new_file.absolute_path)
    new_metadata = new_parsed.frontmatter.copy()
    new_metadata["supersedes"] = request.old_note_id
    new_metadata["updated_at"] = datetime.utcnow().isoformat() + "Z"

    # Format new note content
    new_content_lines = ["---"]
    for key, value in new_metadata.items():
        if value is not None:
            if isinstance(value, list):
                new_content_lines.append(f"{key}: {', '.join(map(str, value))}")
            else:
                new_content_lines.append(f"{key}: {value}")
    new_content_lines.append("---")
    new_content_lines.append("")
    new_content_lines.append(new_parsed.content)
    new_full_content = "\n".join(new_content_lines)

    # Write both files
    await vault_manager.write_file(
        old_note.relative_path, old_full_content, vault=old_note.vault_name
    )
    await vault_manager.write_file(
        new_note.relative_path, new_full_content, vault=new_note.vault_name
    )

    # Re-index both notes
    old_note.frontmatter = old_metadata
    old_note.updated_at = datetime.utcnow()
    await search_index.index_note(old_note)

    new_note.frontmatter = new_metadata
    new_note.updated_at = datetime.utcnow()
    await search_index.index_note(new_note)

    return NoteSupersedResponse(
        old_note_id=request.old_note_id,
        new_note_id=request.new_note_id,
        old_note_title=old_note.title,
        new_note_title=new_note.title,
        message=f"Note '{old_note.title}' superseded by '{new_note.title}'",
    )