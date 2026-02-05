"""Pydantic schemas for search operations.

These schemas are used for the Postgres full-text search service (search_index_pg.py)
and provide a consistent interface across search implementations.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchQuery(BaseModel):
    """Search query parameters for Postgres full-text search.

    Supports:
    - Plain text queries (tokens ANDed together)
    - Quoted phrases (exact sequence matching with <->)
    - Prefix matching with * suffix
    """

    query: str = Field(
        ...,
        description="Search query text. Supports plain words, quoted phrases, and prefix matching.",
        min_length=1,
        max_length=1000,
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination",
    )


class SearchResult(BaseModel):
    """Single search result with relevance ranking.

    Contains the note metadata plus a highlighted snippet showing
    where the search terms matched.
    """

    model_config = ConfigDict(from_attributes=True)

    note_id: UUID = Field(..., description="Unique note identifier")
    path: str = Field(..., description="Vault-style path (e.g., 'projects/my-project/design.md')")
    title: str = Field(..., description="Note title")
    snippet: str = Field(
        ...,
        description="Highlighted excerpt showing where search terms matched. "
        "Uses <b> tags for highlighting by default.",
    )
    rank: float = Field(
        ...,
        description="Relevance score from ts_rank. Higher values indicate better matches.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Last modification timestamp",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Creation timestamp",
    )


class SearchResults(BaseModel):
    """Paginated search results with query metadata."""

    results: list[SearchResult] = Field(
        default_factory=list,
        description="List of search results ordered by relevance",
    )
    total_count: int = Field(
        ...,
        description="Total number of matching notes (for pagination)",
    )
    query: str = Field(..., description="The original search query")
    took_ms: float = Field(
        ...,
        description="Query execution time in milliseconds",
    )
    limit: int = Field(..., description="Maximum results requested")
    offset: int = Field(..., description="Offset for pagination")
