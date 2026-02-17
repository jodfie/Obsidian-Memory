"""Data models for search index."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.note import DecayClass, Observation, Relation, Wikilink


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

    # BM25 ranking parameters
    # Note: k1 and b are reserved for future custom ranking function implementation.
    # FTS5 uses fixed values (k1=1.2, b=0.75). Field boosting is the primary tuning mechanism.
    bm25_k1: float | None = Field(
        default=None,
        ge=0.0,
        le=3.0,
        description="Reserved: BM25 k1 parameter (not currently customizable in FTS5)"
    )
    bm25_b: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Reserved: BM25 b parameter (not currently customizable in FTS5)"
    )
    boost_title: float = Field(
        default=2.0,
        ge=0.0,
        le=10.0,
        description="Title field boost multiplier"
    )
    boost_tags: float = Field(
        default=1.5,
        ge=0.0,
        le=10.0,
        description="Tags field boost multiplier"
    )
    boost_observations: float = Field(
        default=1.3,
        ge=0.0,
        le=10.0,
        description="Observations field boost multiplier"
    )
    recency_boost: bool = Field(
        default=False,
        description="DEPRECATED: Ignored. Replaced by always-on freshness component in composite scoring."
    )
    recency_decay: float = Field(
        default=0.5,
        ge=0.0,
        le=2.0,
        description="DEPRECATED: Ignored. Replaced by always-on freshness component in composite scoring."
    )
    include_expired: bool = Field(
        default=False,
        description="Include expired and low-confidence notes in results"
    )

    # Snippet generation parameters
    snippet_max_length: int = Field(
        default=200,
        ge=50,
        le=1000,
        description="Maximum snippet length in characters"
    )
    snippet_context_tokens: int = Field(
        default=32,
        ge=8,
        le=128,
        description="Number of tokens of context around matches"
    )
    snippet_highlight_start: str = Field(
        default="<mark>",
        description="HTML marker for start of highlight"
    )
    snippet_highlight_end: str = Field(
        default="</mark>",
        description="HTML marker for end of highlight"
    )
    snippet_html_safe: bool = Field(
        default=True,
        description="Return HTML-safe snippets (escaped)"
    )
    snippet_multi_field: bool = Field(
        default=True,
        description="Include snippets from multiple fields (title, content, tags, observations)"
    )


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
    score: float = Field(..., description="Composite relevance score")
    score_breakdown: dict[str, float] | None = Field(
        default=None, description="Breakdown of composite score components"
    )
    decay_class: str | None = Field(default=None, description="Decay classification")
    confidence: float | None = Field(default=None, description="Note confidence (0.0-1.0)")
    created_at: datetime | None = Field(default=None, description="Created at")
    updated_at: datetime | None = Field(default=None, description="Updated at")
    tags: list[str] = Field(default_factory=list, description="Tags")


class SearchResults(BaseModel):
    """Search results with pagination."""

    results: list[SearchResult] = Field(
        default_factory=list, description="Search results"
    )
    total_count: int = Field(..., description="Total result count")
    query: str = Field(..., description="Query string")
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
    decay_class: DecayClass = Field(default='stable', description="Decay tier classification")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Decay confidence score")
    expires_at: datetime | None = Field(default=None, description="Expiration timestamp")
    last_accessed_at: datetime | None = Field(default=None, description="Last search access time")
