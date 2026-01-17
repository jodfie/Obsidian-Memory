"""Pydantic models for data validation."""

from app.models.graph import (
    Edge,
    EdgeType,
    Graph,
    GraphPath,
    Node,
    PathStep,
    TraversalQuery,
    TraversalResult,
)
from app.models.note import (
    Frontmatter,
    NoteType,
    Observation,
    ObservationCategory,
    ParsedNote,
    Relation,
    RelationType,
    Wikilink,
)
from app.models.ai import (
    DeduplicationSuggestion,
    DeduplicationSuggestions,
    DetectedPattern,
    DetectedPatterns,
    Entity,
    EntityType,
    ExtractedEntities,
    InferredRelation,
    InferredRelations,
    SessionSummary,
)
from app.models.search import (
    IndexedNote,
    SearchQuery,
    SearchResult,
    SearchResults,
    SortOrder,
)
from app.models.session import (
    Session,
    SessionEvent,
    SessionEventType,
    SessionContextRequest,
    SessionObserveRequest,
)
from app.models.sync import (
    SyncQueueItem,
    SyncResult,
    SyncStatus,
)
from app.models.vault import (
    VaultConfig,
    VaultFile,
    VaultManagerConfig,
)

__all__ = [
    "DeduplicationSuggestion",
    "DeduplicationSuggestions",
    "DetectedPattern",
    "DetectedPatterns",
    "Edge",
    "EdgeType",
    "Entity",
    "EntityType",
    "ExtractedEntities",
    "Frontmatter",
    "Graph",
    "IndexedNote",
    "InferredRelation",
    "InferredRelations",
    "Node",
    "NoteType",
    "Observation",
    "ObservationCategory",
    "ParsedNote",
    "Relation",
    "RelationType",
    "SearchQuery",
    "SearchResult",
    "SearchResults",
    "Session",
    "SessionContextRequest",
    "SessionEvent",
    "SessionEventType",
    "SessionObserveRequest",
    "SessionSummary",
    "SortOrder",
    "SyncQueueItem",
    "SyncResult",
    "SyncStatus",
    "VaultConfig",
    "VaultFile",
    "VaultManagerConfig",
    "Wikilink",
]
