"""Data models for knowledge graph."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    """Type of edge in the knowledge graph."""

    # Relation-based edges
    DEPENDS_ON = "depends_on"
    ENABLES = "enables"
    RELATED_TO = "related_to"
    LEARNED_FROM = "learned_from"
    SUPERSEDES = "supersedes"
    CAUSED_BY = "caused_by"
    SOLVED_BY = "solved_by"
    PART_OF = "part_of"
    IMPLEMENTS = "implements"
    TESTS = "tests"
    DOCUMENTS = "documents"

    # Wikilink-based edges
    LINKS_TO = "links_to"  # Generic wikilink
    BACKLINK = "backlink"  # Reverse of links_to


class Node(BaseModel):
    """A node in the knowledge graph representing a note."""

    id: int | None = Field(default=None, description="Note ID from index")
    title: str = Field(..., description="Note title")
    permalink: str | None = Field(default=None, description="Permalink")
    vault_name: str = Field(..., description="Vault name")
    relative_path: str = Field(..., description="Relative path")
    note_type: str = Field(..., description="Note type")
    project: str | None = Field(default=None, description="Project")
    tags: list[str] = Field(default_factory=list, description="Tags")
    created_at: datetime | None = Field(default=None, description="Created at")
    updated_at: datetime | None = Field(default=None, description="Updated at")


class Edge(BaseModel):
    """An edge in the knowledge graph representing a relationship."""

    source_id: int = Field(..., description="Source note ID")
    target_id: int | None = Field(default=None, description="Target note ID (if resolved)")
    target_title: str = Field(..., description="Target note title")
    edge_type: EdgeType = Field(..., description="Type of edge")
    context: str | None = Field(default=None, description="Additional context")
    weight: float = Field(default=1.0, description="Edge weight (for ranking)")


class Graph(BaseModel):
    """Knowledge graph structure."""

    nodes: dict[int, Node] = Field(
        default_factory=dict, description="Nodes by ID"
    )
    edges: list[Edge] = Field(
        default_factory=list, description="List of edges"
    )
    title_to_id: dict[str, int] = Field(
        default_factory=dict, description="Title to ID mapping"
    )
    permalink_to_id: dict[str, int] = Field(
        default_factory=dict, description="Permalink to ID mapping"
    )
