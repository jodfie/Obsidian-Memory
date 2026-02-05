"""Pydantic schemas for graph operations.

These schemas are used for API request/response validation and serialization
when working with the Postgres-backed graph engine.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RelationInfo(BaseModel):
    """Information about a relation between notes.

    Used when querying backlinks, outgoing links, and other relation queries.
    """

    model_config = ConfigDict(from_attributes=True)

    source_id: UUID = Field(..., description="UUID of the source note")
    source_path: str = Field(..., description="Vault-style path of the source note")
    target_path: str = Field(..., description="Vault-style path of the target note")
    relation_type: str = Field(
        ..., description="Type of relation (wikilink, tag, depends_on, etc.)"
    )
    context: str | None = Field(
        default=None, description="Surrounding text for context"
    )


class GraphNode(BaseModel):
    """A node in the knowledge graph.

    Represents a note with minimal information for graph visualization.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique note identifier")
    path: str = Field(..., description="Vault-style path")
    title: str = Field(..., description="Note title")


class GraphEdge(BaseModel):
    """An edge in the knowledge graph.

    Represents a relation between two notes.
    """

    model_config = ConfigDict(from_attributes=True)

    source_id: UUID = Field(..., description="UUID of the source note")
    target_id: UUID = Field(..., description="UUID of the target note")
    relation_type: str = Field(
        ..., description="Type of relation (wikilink, tag, depends_on, etc.)"
    )


class Graph(BaseModel):
    """A knowledge graph consisting of nodes and edges.

    Returned from graph traversal operations like get_related_notes.
    """

    model_config = ConfigDict(from_attributes=True)

    nodes: list[GraphNode] = Field(
        default_factory=list, description="List of nodes in the graph"
    )
    edges: list[GraphEdge] = Field(
        default_factory=list, description="List of edges in the graph"
    )
