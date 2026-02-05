"""API v1 endpoints for Postgres-backed graph operations.

This module provides FastAPI endpoints for knowledge graph operations using
PostgresGraphEngine for database-backed graph traversal.

All endpoints enforce user isolation through the user_id parameter.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_id, get_graph_engine_pg
from app.schemas.graph import Graph, GraphNode, RelationInfo
from app.services.graph_engine_pg import PostgresGraphEngine


# Response models for API documentation
class ErrorResponse(BaseModel):
    """Standard error response format."""

    detail: str = Field(..., description="Error message describing what went wrong")
    code: str | None = Field(None, description="Optional error code for client handling")


class BacklinksResponse(BaseModel):
    """Response for backlinks query."""

    note_id: UUID = Field(..., description="ID of the note queried")
    backlinks: list[RelationInfo] = Field(
        ..., description="List of notes that link to this note"
    )
    count: int = Field(..., description="Number of backlinks")

    model_config = {
        "json_schema_extra": {
            "example": {
                "note_id": "550e8400-e29b-41d4-a716-446655440000",
                "backlinks": [
                    {
                        "source_id": "550e8400-e29b-41d4-a716-446655440001",
                        "source_path": "projects/overview.md",
                        "target_path": "projects/api/design.md",
                        "relation_type": "wikilink",
                        "context": "See [[design]] for implementation details",
                    }
                ],
                "count": 1,
            }
        }
    }


class OutgoingLinksResponse(BaseModel):
    """Response for outgoing links query."""

    note_id: UUID = Field(..., description="ID of the note queried")
    outgoing_links: list[RelationInfo] = Field(
        ..., description="List of notes this note links to"
    )
    count: int = Field(..., description="Number of outgoing links")


class TagInfo(BaseModel):
    """Information about a tag and its usage count."""

    tag: str = Field(..., description="Tag name (without # prefix)")
    count: int = Field(..., description="Number of notes with this tag")

    model_config = {
        "json_schema_extra": {"example": {"tag": "python", "count": 42}}
    }


class TagsListResponse(BaseModel):
    """Response for tags list query."""

    tags: list[TagInfo] = Field(..., description="List of tags with usage counts")
    total: int = Field(..., description="Total number of unique tags")


class NotesByTagResponse(BaseModel):
    """Response for notes by tag query."""

    tag: str = Field(..., description="The queried tag")
    notes: list[GraphNode] = Field(..., description="Notes with this tag")
    count: int = Field(..., description="Number of notes with this tag")


# Router configuration
router = APIRouter(
    prefix="/graph",
    tags=["Graph (Postgres)"],
    responses={
        401: {
            "description": "Authentication required",
            "model": ErrorResponse,
        },
        403: {
            "description": "Forbidden",
            "model": ErrorResponse,
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse,
        },
    },
)


@router.get(
    "/{note_id}/backlinks",
    response_model=BacklinksResponse,
    summary="Get backlinks for a note",
    description="""
    Get all notes that link TO the specified note (incoming links).

    Backlinks are useful for:
    - Understanding what references a note
    - Building bidirectional navigation
    - Finding related content
    """,
    responses={
        200: {
            "description": "Backlinks retrieved successfully",
            "model": BacklinksResponse,
        },
    },
)
async def get_backlinks(
    note_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    graph_engine: PostgresGraphEngine = Depends(get_graph_engine_pg),
) -> BacklinksResponse:
    """Get all notes that link to the specified note.

    Returns a list of RelationInfo objects containing:
    - Source note information
    - Relation type (wikilink, tag, etc.)
    - Context snippet where the link appears
    """
    backlinks = await graph_engine.get_backlinks(note_id=note_id, user_id=user_id)

    return BacklinksResponse(
        note_id=note_id,
        backlinks=backlinks,
        count=len(backlinks),
    )


@router.get(
    "/{note_id}/outgoing",
    response_model=OutgoingLinksResponse,
    summary="Get outgoing links from a note",
    description="""
    Get all notes that the specified note links TO (outgoing links).

    Useful for:
    - Understanding what a note references
    - Building forward navigation
    - Analyzing note dependencies
    """,
    responses={
        200: {
            "description": "Outgoing links retrieved successfully",
            "model": OutgoingLinksResponse,
        },
    },
)
async def get_outgoing_links(
    note_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    graph_engine: PostgresGraphEngine = Depends(get_graph_engine_pg),
) -> OutgoingLinksResponse:
    """Get all notes that the specified note links to.

    Returns a list of RelationInfo objects with outgoing link information.
    """
    outgoing = await graph_engine.get_outgoing_links(note_id=note_id, user_id=user_id)

    return OutgoingLinksResponse(
        note_id=note_id,
        outgoing_links=outgoing,
        count=len(outgoing),
    )


@router.get(
    "/{note_id}/related",
    response_model=Graph,
    summary="Get related notes graph",
    description="""
    Get a local subgraph of notes related to the specified note.

    Uses breadth-first traversal to find all notes within `max_depth`
    hops of the starting note. Includes both incoming and outgoing links.

    This is useful for:
    - Graph visualization
    - Finding clusters of related content
    - Understanding knowledge structure
    """,
    responses={
        200: {
            "description": "Graph retrieved successfully",
            "model": Graph,
        },
    },
)
async def get_related_notes(
    note_id: UUID,
    max_depth: int = Query(
        default=2,
        ge=1,
        le=5,
        description="Maximum traversal depth from the starting note",
    ),
    user_id: UUID = Depends(get_current_user_id),
    graph_engine: PostgresGraphEngine = Depends(get_graph_engine_pg),
) -> Graph:
    """Get a local subgraph around the specified note.

    Returns a Graph object containing:
    - nodes: GraphNode objects for each note in the subgraph
    - edges: GraphEdge objects representing links between notes

    The graph is limited to notes within max_depth hops of the starting note.
    """
    graph = await graph_engine.get_related_notes(
        note_id=note_id, user_id=user_id, max_depth=max_depth
    )
    return graph


@router.get(
    "/tags",
    response_model=TagsListResponse,
    summary="Get all tags",
    description="""
    Get all tags used by the user with their usage counts.

    Tags are sorted by count (most used first).
    """,
    responses={
        200: {
            "description": "Tags retrieved successfully",
            "model": TagsListResponse,
        },
    },
)
async def get_all_tags(
    user_id: UUID = Depends(get_current_user_id),
    graph_engine: PostgresGraphEngine = Depends(get_graph_engine_pg),
) -> TagsListResponse:
    """Get all tags with usage counts.

    Returns tags sorted by usage count (descending).
    """
    tags_with_counts = await graph_engine.get_all_tags(user_id=user_id)

    tags = [TagInfo(tag=tag, count=count) for tag, count in tags_with_counts]

    return TagsListResponse(
        tags=tags,
        total=len(tags),
    )


@router.get(
    "/tags/{tag}",
    response_model=NotesByTagResponse,
    summary="Get notes by tag",
    description="""
    Get all notes that have a specific tag.

    The tag can be specified with or without the # prefix.
    """,
    responses={
        200: {
            "description": "Notes retrieved successfully",
            "model": NotesByTagResponse,
        },
    },
)
async def get_notes_by_tag(
    tag: str,
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of notes to return",
    ),
    user_id: UUID = Depends(get_current_user_id),
    graph_engine: PostgresGraphEngine = Depends(get_graph_engine_pg),
) -> NotesByTagResponse:
    """Get all notes with a specific tag.

    The tag name is normalized (# prefix removed if present).
    """
    notes = await graph_engine.get_notes_by_tag(
        tag=tag, user_id=user_id, limit=limit
    )

    return NotesByTagResponse(
        tag=tag.lstrip("#"),
        notes=notes,
        count=len(notes),
    )
