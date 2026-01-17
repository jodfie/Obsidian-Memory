"""API endpoints for notes CRUD operations."""

import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_markdown_parser,
    get_search_index,
    get_vault_manager,
)
from app.api.models import (
    NoteCreateRequest,
    NoteListResponse,
    NoteResponse,
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

router = APIRouter(prefix="/api/notes", tags=["notes"])


async def _ensure_search_index_initialized(
    search_index: SearchIndex,
) -> None:
    """Ensure search index is initialized."""
    if not search_index.db:
        await search_index.initialize()


@router.get("", response_model=NoteListResponse)
async def list_notes(
    vault: str | None = None,
    project: str | None = None,
    limit: int = 50,
    offset: int = 0,
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteListResponse:
    """List notes with optional filtering."""
    # Enforce maximum limit to prevent performance issues
    limit = min(limit, 500)
    
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
    notes: list[NoteResponse] = []
    for result in results.results:
        # Get full note content from vault
        try:
            content = await vault_manager.read_file(
                result.vault_name, result.relative_path
            )
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

    return NoteListResponse(
        notes=notes, total=results.total_count, limit=limit, offset=offset
    )


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    request: NoteCreateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteResponse:
    """Create a new note."""
    await _ensure_search_index_initialized(search_index)

    # Determine vault
    vault_name = request.vault_name
    if not vault_name:
        try:
            default_vault = vault_manager._config.default_vault
            if default_vault:
                vault_name = default_vault
            else:
                vaults = vault_manager.list_vaults()
                if not vaults:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No vaults configured",
                    )
                vault_name = vaults[0].name
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not determine vault: {e}",
            ) from e

    # Parse markdown content
    try:
        parsed = markdown_parser.parse(request.content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid markdown: {e}",
        ) from e

    # Update parsed note with request data
    parsed.frontmatter.title = request.title
    parsed.frontmatter.type = request.note_type
    parsed.frontmatter.project = request.project
    parsed.frontmatter.tags = request.tags

    # Serialize back to markdown
    content = markdown_parser.serialize(parsed)

    # Write to vault
    try:
        await vault_manager.write_file(vault_name, request.relative_path, content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write file: {e}",
        ) from e

    # Index the note
    file_hash = compute_file_hash(content)
    indexed_note = IndexedNote(
        vault_name=vault_name,
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
        file_hash=file_hash,
    )

    note_id = await search_index.index_note(indexed_note)

    return NoteResponse(
        id=note_id,
        vault_name=vault_name,
        relative_path=request.relative_path,
        permalink=parsed.frontmatter.permalink,
        title=parsed.frontmatter.title,
        note_type=parsed.frontmatter.type.value,
        project=parsed.frontmatter.project,
        content=content,
        tags=parsed.frontmatter.tags,
        created_at=indexed_note.created_at,
        updated_at=indexed_note.updated_at,
    )


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: int,
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteResponse:
    """Get a note by ID."""
    await _ensure_search_index_initialized(search_index)

    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    # Get full content from vault
    try:
        content = await vault_manager.read_file(
            indexed_note.vault_name, indexed_note.relative_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {e}",
        ) from e

    return NoteResponse(
        id=note_id,
        vault_name=indexed_note.vault_name,
        relative_path=indexed_note.relative_path,
        permalink=indexed_note.permalink,
        title=indexed_note.title,
        note_type=indexed_note.note_type,
        project=indexed_note.project,
        content=content,
        tags=indexed_note.tags,
        created_at=indexed_note.created_at,
        updated_at=indexed_note.updated_at,
    )


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    request: NoteUpdateRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteResponse:
    """Update an existing note."""
    await _ensure_search_index_initialized(search_index)

    # Get existing note
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    # Read current content
    try:
        content = await vault_manager.read_file(
            indexed_note.vault_name, indexed_note.relative_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {e}",
        ) from e

    # Parse and update
    try:
        parsed = markdown_parser.parse(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid markdown: {e}",
        ) from e

    # Update fields
    if request.title is not None:
        parsed.frontmatter.title = request.title
    if request.note_type is not None:
        parsed.frontmatter.type = request.note_type
    if request.project is not None:
        parsed.frontmatter.project = request.project
    if request.tags is not None:
        parsed.frontmatter.tags = request.tags

    # Update content if provided
    if request.content is not None:
        # Re-parse the new content
        parsed = markdown_parser.parse(request.content)
        # Preserve updated fields
        if request.title is not None:
            parsed.frontmatter.title = request.title
        if request.note_type is not None:
            parsed.frontmatter.type = request.note_type
        if request.project is not None:
            parsed.frontmatter.project = request.project
        if request.tags is not None:
            parsed.frontmatter.tags = request.tags

    # Update timestamp
    parsed.frontmatter.updated = datetime.utcnow()

    # Serialize back to markdown
    content = markdown_parser.serialize(parsed)

    # Write to vault
    try:
        await vault_manager.write_file(
            indexed_note.vault_name, indexed_note.relative_path, content
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write file: {e}",
        ) from e

    # Re-index the note
    file_hash = compute_file_hash(content)
    updated_note = IndexedNote(
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
        file_hash=file_hash,
    )

    await search_index.index_note(updated_note)

    return NoteResponse(
        id=note_id,
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


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: int,
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
) -> None:
    """Delete a note."""
    await _ensure_search_index_initialized(search_index)

    # Get note to find vault and path
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    # Delete from vault
    try:
        await vault_manager.delete_file(
            indexed_note.vault_name, indexed_note.relative_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {e}",
        ) from e

    # Remove from index
    await search_index.remove_note(
        indexed_note.vault_name, indexed_note.relative_path
    )


@router.post("/search", response_model=NoteListResponse)
async def search_notes(
    request: SearchRequest,
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteListResponse:
    """Search notes with full-text search."""
    await _ensure_search_index_initialized(search_index)

    # Build search query
    query = SearchQuery(
        query=request.query,
        vault=request.vault,
        project=request.project,
        note_type=request.note_type,
        tags=request.tags,
        tags_any=request.tags_any,
        sort=request.sort,
        limit=request.limit,
        offset=request.offset,
    )

    results = await search_index.search(query)

    # Convert to response models
    notes: list[NoteResponse] = []
    for result in results.results:
        # Get full note content from vault
        try:
            content = await vault_manager.read_file(
                result.vault_name, result.relative_path
            )
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

    return NoteListResponse(
        notes=notes, total=results.total_count, limit=request.limit, offset=request.offset
    )
