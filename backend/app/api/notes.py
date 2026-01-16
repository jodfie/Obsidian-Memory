"""Notes API endpoints."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import (
    get_markdown_parser,
    get_search_index,
    get_vault_manager,
)
from app.api.models import (
    ErrorResponse,
    NoteCreateRequest,
    NoteListResponse,
    NoteResponse,
    NoteUpdateRequest,
)
from app.models.search import SearchQuery, SortOrder
from app.services.exceptions import (
    VaultNotFoundError,
    VaultReadOnlyError,
)
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex, compute_file_hash
from app.services.vault_manager import VaultManager

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get(
    "",
    response_model=NoteListResponse,
    summary="List or search notes",
    description="List notes with optional search query and filters",
)
async def list_notes(
    q: str | None = Query(None, description="Search query"),
    vault: str | None = Query(None, description="Filter by vault"),
    project: str | None = Query(None, description="Filter by project"),
    note_type: str | None = Query(None, description="Filter by note type"),
    tags: str | None = Query(None, description="Comma-separated tags (AND)"),
    tags_any: str | None = Query(None, description="Comma-separated tags (OR)"),
    sort: SortOrder = Query(SortOrder.RELEVANCE, description="Sort order"),
    limit: int = Query(50, ge=1, le=1000, description="Result limit"),
    offset: int = Query(0, ge=0, description="Result offset"),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteListResponse:
    """List or search notes."""
    if q:
        # Perform search
        query = SearchQuery(
            query=q,
            vault=vault,
            project=project,
            note_type=note_type,
            tags=tags.split(",") if tags else [],
            tags_any=tags_any.split(",") if tags_any else [],
            sort=sort,
            limit=limit,
            offset=offset,
        )
        results = await search_index.search(query)
        return NoteListResponse(
            results=results.results,
            total_count=results.total_count,
            query=q,
            took_ms=results.took_ms,
        )
    else:
        # List recent notes
        results_list = await search_index.get_recent_notes(
            limit=limit, vault=vault, project=project
        )
        return NoteListResponse(
            results=results_list,
            total_count=len(results_list),
            query=None,
            took_ms=0.0,
        )


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get note by ID",
    description="Get a note by its ID from the search index",
)
async def get_note(
    note_id: int,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    parser: MarkdownParser = Depends(get_markdown_parser),
) -> NoteResponse:
    """Get a note by ID."""
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with ID {note_id} not found",
        )

    # Get full content from vault
    try:
        vault_file = await vault_manager.read_file(
            indexed_note.relative_path, vault=indexed_note.vault_name
        )
        content = vault_file.content
    except (FileNotFoundError, VaultNotFoundError):
        # Fallback to indexed content if vault file not available
        content = indexed_note.content

    # Parse the note
    parsed = parser.parse(content)

    return NoteResponse(
        id=note_id,
        vault_name=indexed_note.vault_name,
        relative_path=indexed_note.relative_path,
        permalink=indexed_note.permalink,
        title=parsed.frontmatter.title,
        note_type=parsed.frontmatter.type.value,
        project=parsed.frontmatter.project,
        content=content,
        tags=parsed.frontmatter.tags,
        created_at=parsed.frontmatter.created,
        updated_at=parsed.frontmatter.updated,
        parsed=parsed,
    )


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new note",
    description="Create a new note in a vault",
)
async def create_note(
    request: NoteCreateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    parser: MarkdownParser = Depends(get_markdown_parser),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteResponse:
    """Create a new note."""
    # Build content with frontmatter
    # If content doesn't have frontmatter, add it
    if not request.content.strip().startswith("---"):
        # Add frontmatter
        frontmatter_lines = ["---"]
        frontmatter_lines.append(f"title: {request.title}")
        frontmatter_lines.append(f"type: {request.note_type}")
        if request.project:
            frontmatter_lines.append(f"project: {request.project}")
        if request.tags:
            frontmatter_lines.append(f"tags: {request.tags}")
        frontmatter_lines.append("---")
        frontmatter_lines.append("")
        updated_content = "\n".join(frontmatter_lines) + request.content
    else:
        # Parse and update existing frontmatter
        parsed = parser.parse(request.content)
        frontmatter_updates = {
            "title": request.title,
            "type": request.note_type,
        }
        if request.project:
            frontmatter_updates["project"] = request.project
        if request.tags:
            frontmatter_updates["tags"] = request.tags
        updated_content = parser.update_frontmatter(request.content, frontmatter_updates)

    # Write to vault
    try:
        vault_file = await vault_manager.write_file(
            request.relative_path,
            updated_content,
            vault=request.vault_name,
        )
    except VaultReadOnlyError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except VaultNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Re-parse with updated content
    parsed = parser.parse(updated_content)

    # Index the note
    from app.models.search import IndexedNote

    indexed_note = IndexedNote(
        vault_name=request.vault_name,
        relative_path=request.relative_path,
        permalink=parsed.frontmatter.permalink,
        title=parsed.frontmatter.title,
        note_type=parsed.frontmatter.type.value,
        project=parsed.frontmatter.project,
        content=parsed.raw_content,
        tags=parsed.frontmatter.tags,
        observations=parsed.observations,
        relations=parsed.relations,
        wikilinks=parsed.wikilinks,
        created_at=parsed.frontmatter.created or datetime.utcnow(),
        updated_at=parsed.frontmatter.updated or datetime.utcnow(),
        file_hash=compute_file_hash(updated_content),
    )
    note_id = await search_index.index_note(indexed_note)

    return NoteResponse(
        id=note_id,
        vault_name=request.vault_name,
        relative_path=request.relative_path,
        permalink=parsed.frontmatter.permalink,
        title=parsed.frontmatter.title,
        note_type=parsed.frontmatter.type.value,
        project=parsed.frontmatter.project,
        content=updated_content,
        tags=parsed.frontmatter.tags,
        created_at=parsed.frontmatter.created,
        updated_at=parsed.frontmatter.updated,
        parsed=parsed,
    )


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update a note",
    description="Update an existing note",
)
async def update_note(
    note_id: int,
    request: NoteUpdateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    parser: MarkdownParser = Depends(get_markdown_parser),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteResponse:
    """Update a note."""
    # Get existing note
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with ID {note_id} not found",
        )

    # Get current content
    try:
        vault_file = await vault_manager.read_file(
            indexed_note.relative_path, vault=indexed_note.vault_name
        )
        current_content = vault_file.content
    except (FileNotFoundError, VaultNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note file not found: {e}",
        )

    # Parse current content
    parsed = parser.parse(current_content)

    # Build update content
    if request.content:
        updated_content = request.content
    else:
        updated_content = current_content

    # Update frontmatter if needed
    frontmatter_updates = {}
    if request.title:
        frontmatter_updates["title"] = request.title
    if request.note_type:
        frontmatter_updates["type"] = request.note_type
    if request.project is not None:
        frontmatter_updates["project"] = request.project
    if request.tags is not None:
        frontmatter_updates["tags"] = request.tags

    if frontmatter_updates:
        frontmatter_updates["updated"] = datetime.utcnow().isoformat()
        updated_content = parser.update_frontmatter(updated_content, frontmatter_updates)

    # Write to vault
    try:
        vault_file = await vault_manager.write_file(
            indexed_note.relative_path,
            updated_content,
            vault=indexed_note.vault_name,
        )
    except VaultReadOnlyError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    # Re-parse
    parsed = parser.parse(updated_content)

    # Re-index
    from app.models.search import IndexedNote

    updated_indexed = IndexedNote(
        vault_name=indexed_note.vault_name,
        relative_path=indexed_note.relative_path,
        permalink=parsed.frontmatter.permalink,
        title=parsed.frontmatter.title,
        note_type=parsed.frontmatter.type.value,
        project=parsed.frontmatter.project,
        content=parsed.raw_content,
        tags=parsed.frontmatter.tags,
        observations=parsed.observations,
        relations=parsed.relations,
        wikilinks=parsed.wikilinks,
        created_at=parsed.frontmatter.created or indexed_note.created_at,
        updated_at=parsed.frontmatter.updated or datetime.utcnow(),
        file_hash=compute_file_hash(updated_content),
    )
    await search_index.index_note(updated_indexed)

    return NoteResponse(
        id=note_id,
        vault_name=indexed_note.vault_name,
        relative_path=indexed_note.relative_path,
        permalink=parsed.frontmatter.permalink,
        title=parsed.frontmatter.title,
        note_type=parsed.frontmatter.type.value,
        project=parsed.frontmatter.project,
        content=updated_content,
        tags=parsed.frontmatter.tags,
        created_at=parsed.frontmatter.created,
        updated_at=parsed.frontmatter.updated,
        parsed=parsed,
    )


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    description="Delete a note from both vault and index",
)
async def delete_note(
    note_id: int,
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
) -> None:
    """Delete a note."""
    # Get note info
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with ID {note_id} not found",
        )

    # Delete from vault
    try:
        await vault_manager.delete_file(
            indexed_note.relative_path, vault=indexed_note.vault_name
        )
    except (FileNotFoundError, VaultNotFoundError):
        # File might already be deleted, continue with index removal
        pass
    except VaultReadOnlyError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    # Remove from index
    await search_index.remove_note(
        indexed_note.vault_name, indexed_note.relative_path
    )


@router.get(
    "/{note_id}/backlinks",
    response_model=NoteListResponse,
    summary="Get backlinks",
    description="Get all notes that link to this note",
)
async def get_backlinks(
    note_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteListResponse:
    """Get backlinks for a note."""
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note with ID {note_id} not found",
        )

    backlinks = await search_index.get_backlinks(note_id)

    return NoteListResponse(
        results=backlinks,
        total_count=len(backlinks),
        query=None,
        took_ms=0.0,
    )
