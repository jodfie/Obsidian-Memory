"""API endpoints for per-turn memory recall."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_search_index
from app.config import settings
from app.services.search_index import SearchIndex

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recall", tags=["Recall"])


class RecallConfigResponse(BaseModel):
    """Response model for recall configuration."""

    enabled: bool = Field(..., description="Whether automatic recall is enabled")
    max_results: int = Field(..., description="Maximum memories per recall query")
    min_relevance: float = Field(..., description="Minimum relevance score threshold")
    include_profile: bool = Field(..., description="Include profile in recall context")
    max_snippet_length: int = Field(..., description="Max character length for snippets")


class RecallRequest(BaseModel):
    """Request model for recall search."""

    query: str = Field(..., min_length=1, description="Search query (user prompt text)")
    project: str | None = Field(default=None, description="Optional project filter")
    limit: int | None = Field(default=None, ge=1, le=50, description="Override max results")
    threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Override min relevance"
    )


class RecallMemory(BaseModel):
    """A single recalled memory item."""

    id: int = Field(..., description="Note ID")
    title: str = Field(..., description="Note title")
    snippet: str = Field(..., description="Content snippet")
    note_type: str = Field(..., description="Note type")
    project: str | None = Field(default=None, description="Project")
    score: float = Field(default=0.0, description="Relevance score (0-1)")
    tags: list[str] = Field(default_factory=list, description="Note tags")


class RecallResponse(BaseModel):
    """Response model for recall search results."""

    memories: list[RecallMemory] = Field(default_factory=list)
    query: str = Field(..., description="Original query")
    total_found: int = Field(default=0, description="Total matching memories before limit")
    latency_ms: float = Field(default=0.0, description="Search latency in milliseconds")


@router.get(
    "/config",
    response_model=RecallConfigResponse,
    summary="Get recall configuration",
    description="Returns current recall configuration settings.",
)
async def get_recall_config() -> RecallConfigResponse:
    """Return current recall configuration from settings."""
    return RecallConfigResponse(
        enabled=settings.recall_enabled,
        max_results=settings.recall_max_results,
        min_relevance=settings.recall_min_relevance,
        include_profile=settings.recall_include_profile,
        max_snippet_length=settings.recall_max_snippet_length,
    )


@router.post(
    "/search",
    response_model=RecallResponse,
    summary="Lightweight recall search",
    description="Fast search optimized for per-turn context injection. Returns minimal fields from index only (no vault I/O).",
)
async def recall_search(
    request: RecallRequest,
    search_index: SearchIndex = Depends(get_search_index),
) -> RecallResponse:
    """Lightweight recall search returning indexed data only (no vault file reads).

    Optimized for <200ms latency by:
    - Returning only indexed fields (no vault I/O)
    - Using FTS5 snippets from SQLite
    - Limiting result count
    """
    if not settings.recall_enabled:
        return RecallResponse(query=request.query, memories=[], total_found=0, latency_ms=0.0)

    if not search_index.db:
        await search_index.initialize()

    start = time.monotonic()

    limit = request.limit or settings.recall_max_results
    threshold = request.threshold or settings.recall_min_relevance
    max_snippet = settings.recall_max_snippet_length

    memories = await search_index.search_for_recall(
        query=request.query,
        project=request.project,
        limit=limit,
        min_relevance=threshold,
        max_snippet_length=max_snippet,
    )

    latency_ms = (time.monotonic() - start) * 1000

    if latency_ms > 200:
        logger.warning(f"Recall search exceeded 200ms target: {latency_ms:.1f}ms for query '{request.query[:50]}'")

    return RecallResponse(
        memories=memories,
        query=request.query,
        total_found=len(memories),
        latency_ms=round(latency_ms, 1),
    )
