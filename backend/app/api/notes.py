"""API endpoints for notes CRUD operations."""

import hashlib
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_ai_processor,
    get_markdown_parser,
    get_search_index,
    get_vault_manager,
)
from app.api.models import (
    EntityListResponse,
    EntityResponse,
    EntitySearchRequest,
    EntitySearchResponse,
    EntitySearchResult,
    EntityTypeListResponse,
    ExtractEntitiesRequest,
    ExtractEntitiesResponse,
    NoteCreateRequest,
    NoteListResponse,
    NoteResponse,
    NoteSupersedRequest,
    NoteSupersedResponse,
    NoteUpdateRequest,
    SearchRequest,
)
from app.services.ai_processor import AIProcessor
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
    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 500",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be non-negative",
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
    notes: list[NoteResponse] = []
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
        await vault_manager.write_file(request.relative_path, content, vault=vault_name)
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
        vault_file = await vault_manager.read_file(
            indexed_note.relative_path, vault=indexed_note.vault_name
        )
        content = vault_file.content
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


@router.get("/{note_id}/patterns")
async def get_note_patterns(
    note_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict:
    """Get patterns detected in a note."""
    await _ensure_search_index_initialized(search_index)
    note = await search_index.get_note_by_id(note_id)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )
    patterns = await search_index.get_patterns_for_note(note_id)
    return {"note_id": note_id, "patterns": patterns, "count": len(patterns)}


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
        vault_file = await vault_manager.read_file(
            indexed_note.relative_path, vault=indexed_note.vault_name
        )
        content = vault_file.content
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
            indexed_note.relative_path, content, vault=indexed_note.vault_name
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


class MergeNotesRequest(BaseModel):
    """Request body for merging two notes."""

    target_note_id: int = Field(..., description="Note ID to keep (merged content written here)")
    source_note_id: int = Field(..., description="Note ID to merge in and then remove")


@router.post("/merge", response_model=NoteResponse)
async def merge_notes(
    request: MergeNotesRequest = Body(...),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    search_index: SearchIndex = Depends(get_search_index),
) -> NoteResponse:
    """Merge two notes: combine content into target, remove source."""
    await _ensure_search_index_initialized(search_index)

    target_id = request.target_note_id
    source_id = request.source_note_id
    if target_id == source_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target and source note must differ",
        )

    target_note = await search_index.get_note_by_id(target_id)
    source_note = await search_index.get_note_by_id(source_id)
    if not target_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target note {target_id} not found",
        )
    if not source_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source note {source_id} not found",
        )
    if target_note.vault_name != source_note.vault_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notes must be in the same vault to merge",
        )

    target_file = await vault_manager.read_file(
        target_note.relative_path, vault=target_note.vault_name
    )
    source_file = await vault_manager.read_file(
        source_note.relative_path, vault=source_note.vault_name
    )
    parsed_target = markdown_parser.parse(target_file.content)
    parsed_source = markdown_parser.parse(source_file.content)

    # Merge: union tags, target title, latest dates; combine body with separator
    merged_tags = list(dict.fromkeys(
        (parsed_target.frontmatter.tags or []) + (parsed_source.frontmatter.tags or [])
    ))
    merged_content_body = (
        parsed_target.raw_content.strip()
        + "\n\n---\n\n## Merged from: "
        + (parsed_source.frontmatter.title or source_note.title)
        + "\n\n"
        + parsed_source.raw_content.strip()
    )
    parsed_target.frontmatter.tags = merged_tags
    parsed_target.frontmatter.updated = datetime.utcnow()
    parsed_target.raw_content = merged_content_body
    parsed_target.frontmatter_modified = True

    merged_md = markdown_parser.serialize(parsed_target)
    await vault_manager.write_file(
        target_note.relative_path, merged_md, vault=target_note.vault_name
    )

    file_hash = compute_file_hash(merged_md)
    updated_indexed = IndexedNote(
        vault_name=target_note.vault_name,
        relative_path=target_note.relative_path,
        permalink=target_note.permalink,
        title=parsed_target.frontmatter.title,
        note_type=target_note.note_type,
        project=target_note.project,
        content=merged_content_body,
        tags=merged_tags,
        observations=target_note.observations,
        relations=target_note.relations,
        wikilinks=target_note.wikilinks,
        created_at=target_note.created_at,
        updated_at=parsed_target.frontmatter.updated or datetime.utcnow(),
        file_hash=file_hash,
    )
    await search_index.index_note(updated_indexed)

    await vault_manager.delete_file(
        source_note.relative_path, vault=source_note.vault_name
    )
    await search_index.remove_note(source_note.vault_name, source_note.relative_path)

    await search_index.mark_dedup_suggestion_merged_for_pair(target_id, source_id)

    updated = await search_index.get_note_by_id(target_id)
    if not updated:
        updated = target_note
    content = ""
    try:
        vf = await vault_manager.read_file(
            updated.relative_path, vault=updated.vault_name
        )
        content = vf.content
    except Exception:
        content = merged_md

    return NoteResponse(
        id=target_id,
        vault_name=updated.vault_name,
        relative_path=updated.relative_path,
        permalink=updated.permalink,
        title=updated.title,
        note_type=updated.note_type,
        project=updated.project,
        content=content,
        tags=updated.tags,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
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
            indexed_note.relative_path, vault=indexed_note.vault_name
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

    return NoteListResponse(
        notes=notes, total=results.total_count, limit=request.limit, offset=request.offset
    )


@router.post("/supersede", response_model=NoteSupersedResponse)
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

    Both notes are re-indexed to reflect the relationship in the knowledge graph.
    """
    await _ensure_search_index_initialized(search_index)

    # Get both notes
    old_note = await search_index.get_note_by_id(request.old_note_id)
    if not old_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Old note with ID {request.old_note_id} not found",
        )

    new_note = await search_index.get_note_by_id(request.new_note_id)
    if not new_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"New note with ID {request.new_note_id} not found",
        )

    # Prevent self-supersession
    if request.old_note_id == request.new_note_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A note cannot supersede itself",
        )

    async def _update_note_supersedes(
        note: IndexedNote,
        supersedes_permalink: str | None,
        superseded_by_permalink: str | None,
    ) -> None:
        """Update a note's supersedes/superseded_by fields."""
        # Read current content
        vault_file = await vault_manager.read_file(
            note.relative_path, vault=note.vault_name
        )
        parsed = markdown_parser.parse(vault_file.content)

        # Update supersedes fields
        if supersedes_permalink is not None:
            parsed.frontmatter.supersedes = supersedes_permalink
        if superseded_by_permalink is not None:
            parsed.frontmatter.superseded_by = superseded_by_permalink

        parsed.frontmatter.updated = datetime.utcnow()
        parsed.frontmatter_modified = True

        # Serialize and write back
        content = markdown_parser.serialize(parsed)
        await vault_manager.write_file(
            note.relative_path, content, vault=note.vault_name
        )

        # Re-index the note
        file_hash = compute_file_hash(content)
        updated_indexed = IndexedNote(
            vault_name=note.vault_name,
            relative_path=note.relative_path,
            permalink=parsed.frontmatter.permalink,
            title=parsed.frontmatter.title,
            note_type=parsed.frontmatter.type.value,
            project=parsed.frontmatter.project,
            content=parsed.raw_content,
            tags=parsed.frontmatter.tags,
            observations=parsed.observations,
            relations=parsed.relations,
            wikilinks=parsed.wikilinks,
            created_at=parsed.frontmatter.created or note.created_at,
            updated_at=parsed.frontmatter.updated or datetime.utcnow(),
            file_hash=file_hash,
        )
        await search_index.index_note(updated_indexed)

    # Determine permalinks for linking (use permalink or title as fallback)
    old_permalink = old_note.permalink or old_note.title
    new_permalink = new_note.permalink or new_note.title

    try:
        # Update old note: set superseded_by to new note's permalink
        await _update_note_supersedes(old_note, None, new_permalink)

        # Update new note: set supersedes to old note's permalink
        await _update_note_supersedes(new_note, old_permalink, None)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notes: {e}",
        ) from e

    message = f"Note '{old_note.title}' is now superseded by '{new_note.title}'"
    if request.reason:
        message += f" (reason: {request.reason})"

    return NoteSupersedResponse(
        old_note_id=request.old_note_id,
        new_note_id=request.new_note_id,
        old_note_title=old_note.title,
        new_note_title=new_note.title,
        message=message,
    )


# -----------------------------------------------------------------------------
# Entity Extraction Endpoints
# -----------------------------------------------------------------------------


@router.post("/{note_id}/extract-entities", response_model=ExtractEntitiesResponse)
async def extract_entities(
    note_id: int,
    request: ExtractEntitiesRequest | None = None,
    vault_manager: VaultManager = Depends(get_vault_manager),
    search_index: SearchIndex = Depends(get_search_index),
    ai_processor: AIProcessor = Depends(get_ai_processor),
) -> ExtractEntitiesResponse:
    """Extract entities from a note using AI.

    Uses the AIProcessor to analyze the note content and extract entities like
    PERSON, TOOL, CONCEPT, ERROR, LIBRARY, FRAMEWORK, PATTERN, TECHNIQUE, etc.

    Args:
        note_id: ID of the note to extract entities from
        request: Optional request with force flag to re-extract

    Returns:
        ExtractEntitiesResponse with extracted entities
    """
    await _ensure_search_index_initialized(search_index)

    # Default request if none provided
    if request is None:
        request = ExtractEntitiesRequest()

    # Get the note
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    # Check for existing entities if not forcing re-extraction
    if not request.force:
        existing_entities = await search_index.get_entities(note_id)
        if existing_entities:
            return ExtractEntitiesResponse(
                note_id=note_id,
                entities=[
                    EntityResponse(
                        id=e["id"],
                        entity_type=e["entity_type"],
                        name=e["name"],
                        description=e["description"],
                        confidence=e["confidence"],
                        extracted_at=e["extracted_at"],
                    )
                    for e in existing_entities
                ],
                count=len(existing_entities),
                cached=True,
            )

    # Get full content from vault for better extraction
    try:
        vault_file = await vault_manager.read_file(
            indexed_note.relative_path, vault=indexed_note.vault_name
        )
        content = vault_file.content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read note content: {e}",
        ) from e

    # Extract entities using AI
    try:
        extracted = await ai_processor.extract_entities(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Entity extraction failed: {e}",
        ) from e

    # Convert to storage format and store
    entities_to_store = [
        {
            "entity_type": entity.entity_type.value,
            "name": entity.name,
            "description": entity.description,
            "confidence": entity.confidence,
        }
        for entity in extracted.entities
    ]

    await search_index.store_entities(note_id, entities_to_store, replace_existing=True)

    # Retrieve stored entities to get IDs
    stored_entities = await search_index.get_entities(note_id)

    return ExtractEntitiesResponse(
        note_id=note_id,
        entities=[
            EntityResponse(
                id=e["id"],
                entity_type=e["entity_type"],
                name=e["name"],
                description=e["description"],
                confidence=e["confidence"],
                extracted_at=e["extracted_at"],
            )
            for e in stored_entities
        ],
        count=len(stored_entities),
        cached=False,
    )


@router.get("/{note_id}/entities", response_model=EntityListResponse)
async def get_note_entities(
    note_id: int,
    entity_type: str | None = None,
    min_confidence: float = 0.0,
    search_index: SearchIndex = Depends(get_search_index),
) -> EntityListResponse:
    """Get entities for a specific note.

    Args:
        note_id: ID of the note
        entity_type: Optional filter by entity type
        min_confidence: Minimum confidence threshold (0.0 to 1.0)

    Returns:
        EntityListResponse with the note's entities
    """
    await _ensure_search_index_initialized(search_index)

    # Verify note exists
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    entities = await search_index.get_entities(
        note_id, entity_type=entity_type, min_confidence=min_confidence
    )

    return EntityListResponse(
        note_id=note_id,
        entities=[
            EntityResponse(
                id=e["id"],
                entity_type=e["entity_type"],
                name=e["name"],
                description=e["description"],
                confidence=e["confidence"],
                extracted_at=e["extracted_at"],
            )
            for e in entities
        ],
        total=len(entities),
    )


@router.delete("/{note_id}/entities", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note_entities(
    note_id: int,
    search_index: SearchIndex = Depends(get_search_index),
) -> None:
    """Delete all entities for a note.

    Args:
        note_id: ID of the note to delete entities for
    """
    await _ensure_search_index_initialized(search_index)

    # Verify note exists
    indexed_note = await search_index.get_note_by_id(note_id)
    if not indexed_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    await search_index.delete_entities(note_id)


@router.post("/entities/search", response_model=EntitySearchResponse)
async def search_by_entity(
    request: EntitySearchRequest,
    search_index: SearchIndex = Depends(get_search_index),
) -> EntitySearchResponse:
    """Search for notes containing a specific entity.

    Args:
        request: Search parameters including entity name and optional filters

    Returns:
        EntitySearchResponse with matching notes and their entities
    """
    await _ensure_search_index_initialized(search_index)

    results = await search_index.search_by_entity(
        entity_name=request.entity_name,
        entity_type=request.entity_type,
        min_confidence=request.min_confidence,
        limit=request.limit,
    )

    return EntitySearchResponse(
        results=[
            EntitySearchResult(
                note_id=r["note_id"],
                path=r["path"],
                title=r["title"],
                entity_type=r["entity_type"],
                entity_name=r["entity_name"],
                entity_description=r["entity_description"],
                confidence=r["confidence"],
            )
            for r in results
        ],
        total=len(results),
        query=request.entity_name,
    )


@router.get("/entities/by-type/{entity_type}", response_model=EntityTypeListResponse)
async def get_entities_by_type(
    entity_type: str,
    min_confidence: float = 0.0,
    limit: int = 100,
    search_index: SearchIndex = Depends(get_search_index),
) -> EntityTypeListResponse:
    """Get all unique entities of a specific type across the vault.

    Args:
        entity_type: The entity type to filter by (e.g., PERSON, TOOL, CONCEPT)
        min_confidence: Minimum confidence threshold
        limit: Maximum results

    Returns:
        EntityTypeListResponse with unique entities and occurrence counts
    """
    await _ensure_search_index_initialized(search_index)

    entities = await search_index.get_all_entities_by_type(
        entity_type=entity_type.upper(),
        min_confidence=min_confidence,
        limit=limit,
    )

    return EntityTypeListResponse(
        entity_type=entity_type.upper(),
        entities=entities,
        total=len(entities),
    )
