"""Data models for AI processing results."""

from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Type of extracted entity."""

    PERSON = "person"
    TOOL = "tool"
    CONCEPT = "concept"
    ERROR = "error"
    LIBRARY = "library"
    FRAMEWORK = "framework"
    PATTERN = "pattern"
    TECHNIQUE = "technique"
    PROJECT = "project"
    FILE = "file"
    COMMAND = "command"


class Entity(BaseModel):
    """An extracted entity from content."""

    entity_type: EntityType = Field(..., description="Type of entity")
    name: str = Field(..., description="Entity name")
    description: str | None = Field(
        default=None, description="Brief description or context"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score (0-1)"
    )


class ExtractedEntities(BaseModel):
    """Result of entity extraction."""

    entities: list[Entity] = Field(..., description="Extracted entities")
    note_id: int | None = Field(default=None, description="Source note ID if applicable")


class InferredRelation(BaseModel):
    """An automatically inferred relation between notes."""

    source_note_id: int = Field(..., description="Source note ID")
    target_note_id: int = Field(..., description="Target note ID")
    relation_type: str = Field(..., description="Type of relation")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    reasoning: str | None = Field(
        default=None, description="Explanation for the inference"
    )


class InferredRelations(BaseModel):
    """Result of relation inference."""

    relations: list[InferredRelation] = Field(..., description="Inferred relations")
    note_pairs_analyzed: int = Field(..., description="Number of note pairs analyzed")


class SessionSummary(BaseModel):
    """Summary of a session."""

    key_learnings: list[str] = Field(..., description="Key learnings from session")
    decisions: list[str] = Field(default_factory=list, description="Decisions made")
    errors_encountered: list[str] = Field(
        default_factory=list, description="Errors encountered"
    )
    solutions_found: list[str] = Field(
        default_factory=list, description="Solutions discovered"
    )
    next_steps: list[str] = Field(default_factory=list, description="Suggested next steps")
    summary_text: str = Field(..., description="Overall summary text")
    compression_ratio: float = Field(
        ..., description="Ratio of summary length to original length"
    )
    # Enhanced fields for richer summarization
    topics: list[str] = Field(
        default_factory=list, description="Detected topics/themes from session"
    )
    participants: list[str] = Field(
        default_factory=list, description="People, tools, or systems involved"
    )
    actionable_items: list[str] = Field(
        default_factory=list, description="Items requiring follow-up action"
    )
    related_notes: list[str] = Field(
        default_factory=list, description="Suggested note links or references"
    )
    chunk_count: int = Field(
        default=1, description="Number of chunks summarized (for incremental)"
    )
    is_incremental: bool = Field(
        default=False, description="Whether this was incrementally summarized"
    )


class DetectedPattern(BaseModel):
    """A pattern detected across multiple notes."""

    pattern_name: str = Field(..., description="Name of the pattern")
    description: str = Field(..., description="Pattern description")
    note_ids: list[int] = Field(..., description="Note IDs exhibiting this pattern")
    frequency: int = Field(..., description="Number of occurrences")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    category: str | None = Field(
        default=None, description="Pattern category (solution, technique, etc.)"
    )


class DetectedPatterns(BaseModel):
    """Result of pattern detection."""

    patterns: list[DetectedPattern] = Field(..., description="Detected patterns")
    notes_analyzed: int = Field(..., description="Number of notes analyzed")


class DeduplicationSuggestion(BaseModel):
    """Suggestion for merging duplicate notes."""

    note_ids: list[int] = Field(..., description="Note IDs that appear to be duplicates")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score (0-1)"
    )
    reasoning: str = Field(..., description="Why these notes are considered duplicates")
    suggested_action: str = Field(
        ..., description="Suggested action (merge, link, etc.)"
    )


class DeduplicationSuggestions(BaseModel):
    """Result of deduplication analysis."""

    suggestions: list[DeduplicationSuggestion] = Field(
        ..., description="Deduplication suggestions"
    )
    notes_analyzed: int = Field(..., description="Number of notes analyzed")
