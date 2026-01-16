"""Data models for search index."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.note import Observation, Relation, Wikilink


class SortOrder(str, Enum):
    """Sort order for search results."""

    RELEVANCE = "relevance"
    CREATED_DESC = "created_desc"
    CREATED_ASC = "created_asc"
    UPDATED_DESC = "updated_desc"
    UPDATED_ASC = "updated_asc"
    TITLE_ASC = "title_asc"


class SearchQuery(BaseModel):
    """Search query parameters."""

    query: str = Field(..., description="FTS5 query string")
    vault: str | None = Field(default=None, description="Filter by vault")
    project: str | None = Field(default=None, description="Filter by project")
    note_type: str | None = Field(default=None, description="Filter by type")
    tags: list[str] = Field(
        default_factory=list, description="Filter by tags (AND)"
    )
    tags_any: list[str] = Field(
        default_factory=list, description="Filter by tags (OR)"
    )
    observation_category: str | None = Field(
        default=None, description="Filter by observation type"
    )
    created_after: datetime | None = Field(
        default=None, description="Filter by creation date (after)"
    )
    created_before: datetime | None = Field(
        default=None, description="Filter by creation date (before)"
    )
    sort: SortOrder = Field(
        default=SortOrder.RELEVANCE, description="Sort order"
    )
    limit: int = Field(default=50, ge=1, le=1000, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Result offset")


class SearchResult(BaseModel):
    """Single search result."""

    note_id: int = Field(..., description="Note ID")
    vault_name: str = Field(..., description="Vault name")
    relative_path: str = Field(..., description="Relative path")
    permalink: str | None = Field(default=None, description="Permalink")
    title: str = Field(..., description="Note title")
    note_type: str = Field(..., description="Note type")
    project: str | None = Field(default=None, description="Project")
    snippet: str = Field(..., description="Highlighted excerpt")
    score: float = Field(..., description="Relevance score")
    created_at: datetime | None = Field(default=None, description="Created at")
    updated_at: datetime | None = Field(default=None, description="Updated at")
    tags: list[str] = Field(default_factory=list, description="Tags")


class SearchResults(BaseModel):
    """Search results with pagination."""

    results: list[SearchResult] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total matching count")
    query: str = Field(..., description="Original query")
    took_ms: float = Field(..., description="Query time in milliseconds")


class IndexedNote(BaseModel):
    """Note data for indexing."""

    vault_name: str = Field(..., description="Vault name")
    relative_path: str = Field(..., description="Relative path")
    permalink: str | None = Field(default=None, description="Permalink")
    title: str = Field(..., description="Note title")
    note_type: str = Field(..., description="Note type")
    project: str | None = Field(default=None, description="Project")
    content: str = Field(..., description="Full content for FTS")
    tags: list[str] = Field(default_factory=list, description="Tags")
    observations: list[Observation] = Field(
        default_factory=list, description="Observations"
    )
    relations: list[Relation] = Field(
        default_factory=list, description="Relations"
    )
    wikilinks: list[Wikilink] = Field(
        default_factory=list, description="Wikilinks"
    )
    created_at: datetime | None = Field(default=None, description="Created at")
    updated_at: datetime | None = Field(default=None, description="Updated at")
    file_hash: str = Field(..., description="File hash for change detection")
