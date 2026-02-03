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


class EdgeSource(str, Enum):
    """Source of an edge in the knowledge graph."""

    EXPLICIT = "explicit"  # From frontmatter relations
    WIKILINK = "wikilink"  # From [[wikilinks]]
    INFERRED = "inferred"  # AI-inferred from content similarity


class Edge(BaseModel):
    """An edge in the knowledge graph representing a relationship."""

    edge_id: str | None = Field(default=None, description="Unique edge identifier")
    source_id: int = Field(..., description="Source note ID")
    target_id: int | None = Field(default=None, description="Target note ID (if resolved)")
    target_title: str = Field(..., description="Target note title")
    edge_type: EdgeType = Field(..., description="Type of edge")
    context: str | None = Field(default=None, description="Additional context")
    weight: float = Field(default=1.0, description="Edge weight (for ranking)")
    # Inferred relation fields
    source_type: EdgeSource = Field(
        default=EdgeSource.EXPLICIT, description="How the edge was created"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score (for inferred edges)"
    )
    reasoning: str | None = Field(
        default=None, description="AI reasoning for inferred relations"
    )
    inferred_at: datetime | None = Field(
        default=None, description="When the edge was inferred"
    )

    @property
    def is_inferred(self) -> bool:
        """Check if this edge was AI-inferred."""
        return self.source_type == EdgeSource.INFERRED


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


class PathStep(BaseModel):
    """A single step in a graph path."""

    from_node_id: int = Field(..., description="Source node ID")
    to_node_id: int = Field(..., description="Target node ID")
    edge: Edge = Field(..., description="Edge traversed")
    depth: int = Field(..., description="Depth from start")


class GraphPath(BaseModel):
    """A path through the knowledge graph."""

    steps: list[PathStep] = Field(..., description="Path steps")
    total_weight: float = Field(..., description="Sum of edge weights")
    length: int = Field(..., description="Number of edges")


class TraversalResult(BaseModel):
    """Result of a graph traversal query."""

    visited_nodes: list[int] = Field(..., description="Node IDs visited in order")
    paths: list[GraphPath] = Field(
        default_factory=list, description="Paths found (if path-finding query)"
    )
    depth_reached: int = Field(..., description="Maximum depth reached")


class TraversalQuery(BaseModel):
    """Query parameters for graph traversal."""

    start_node_id: int = Field(..., description="Starting node ID")
    target_node_id: int | None = Field(
        default=None, description="Target node ID (for path-finding)"
    )
    method: str = Field(
        default="bfs", description="Traversal method: 'bfs' or 'dfs'"
    )
    max_depth: int = Field(default=10, ge=1, le=100, description="Maximum traversal depth")
    edge_types: list[EdgeType] | None = Field(
        default=None, description="Filter by edge types (None = all types)"
    )
    direction: str = Field(
        default="outgoing", description="Direction: 'outgoing', 'incoming', or 'both'"
    )
    exclude_nodes: list[int] = Field(
        default_factory=list, description="Node IDs to exclude from traversal"
    )


class BacklinkItem(BaseModel):
    """Information about a single backlink to a note."""

    source_node: Node = Field(..., description="The note that links TO the target")
    edge_type: EdgeType = Field(..., description="Type of relationship")
    context: str | None = Field(default=None, description="Context snippet from source note")
    weight: float = Field(default=1.0, description="Edge weight for ranking")


class BacklinkResponse(BaseModel):
    """Response containing backlinks (notes that link TO a given note)."""

    target_node_id: int = Field(..., description="The note being linked TO")
    target_title: str = Field(..., description="Title of the target note")
    backlinks: list[BacklinkItem] = Field(
        default_factory=list, description="List of backlinks"
    )
    total_count: int = Field(..., description="Total number of backlinks")


class NodeCentrality(BaseModel):
    """Centrality metrics for a graph node."""

    node_id: int = Field(..., description="Node ID")
    title: str | None = Field(default=None, description="Node title")
    permalink: str | None = Field(default=None, description="Node permalink")
    degree_centrality: int = Field(..., description="Total degree (in + out)")
    in_degree: int = Field(..., description="Number of incoming edges")
    out_degree: int = Field(..., description="Number of outgoing edges")
    normalized_centrality: float = Field(..., description="Normalized centrality (0-1)")
    outgoing_by_type: dict[str, int] = Field(
        default_factory=dict, description="Outgoing edge counts by type"
    )
    incoming_by_type: dict[str, int] = Field(
        default_factory=dict, description="Incoming edge counts by type"
    )


class GraphStats(BaseModel):
    """Statistics about the knowledge graph."""

    total_nodes: int = Field(..., description="Total number of nodes")
    total_edges: int = Field(..., description="Total number of edges")
    edge_type_distribution: dict[str, int] = Field(
        default_factory=dict, description="Edge count by type"
    )
    orphan_nodes: list[int] = Field(
        default_factory=list, description="Nodes with no connections"
    )
    orphan_count: int = Field(..., description="Number of orphan nodes")
    average_degree: float = Field(..., description="Average node degree")
    graph_density: float = Field(..., description="Graph density (0-1)")
    top_hubs: list[dict] = Field(
        default_factory=list, description="Most connected nodes"
    )


class HubNode(BaseModel):
    """A hub node with high connectivity."""

    node_id: int = Field(..., description="Node ID")
    title: str = Field(..., description="Node title")
    permalink: str | None = Field(default=None, description="Node permalink")
    degree_centrality: int = Field(..., description="Total degree")
    in_degree: int = Field(..., description="Incoming edges")
    out_degree: int = Field(..., description="Outgoing edges")
    normalized_centrality: float = Field(..., description="Normalized centrality")
