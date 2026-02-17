"""Data models for parsed markdown notes."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class NoteType(str, Enum):
    """Note type enumeration."""

    NOTE = "note"
    DECISION = "decision"
    ERROR = "error"
    KNOWLEDGE = "knowledge"
    PATTERN = "pattern"
    SESSION = "session"
    RESEARCH = "research"
    PROFILE = "profile"


class ObservationCategory(str, Enum):
    """Observation category enumeration."""

    DECISION = "decision"
    REASON = "reason"
    TRADEOFF = "tradeoff"
    IMPLEMENTATION = "implementation"
    GOTCHA = "gotcha"
    PATTERN = "pattern"
    TIP = "tip"
    FACT = "fact"
    ERROR = "error"
    SOLUTION = "solution"
    EXPERIMENT = "experiment"
    RESOURCE = "resource"
    QUESTION = "question"
    ANSWER = "answer"


class RelationType(str, Enum):
    """Relation type enumeration."""

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


# Five-tier decay classification for memory relevance scoring
DecayClass = Literal['permanent', 'stable', 'active', 'session', 'checkpoint']


class Frontmatter(BaseModel):
    """Parsed YAML frontmatter."""

    title: str = Field(..., description="Note title")
    type: NoteType = Field(default=NoteType.NOTE, description="Note type")
    project: str | None = Field(default=None, description="Project identifier")
    permalink: str | None = Field(
        default=None, description="URL-safe slug for linking"
    )
    created: datetime | None = Field(default=None, description="Creation timestamp")
    updated: datetime | None = Field(
        default=None, description="Last update timestamp"
    )
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    supersedes: str | None = Field(
        default=None, description="Permalink of note this replaces"
    )
    superseded_by: str | None = Field(
        default=None, description="Permalink of note that replaced this"
    )
    extra: dict = Field(
        default_factory=dict, description="Any additional frontmatter fields"
    )


class Observation(BaseModel):
    """A structured observation from note content."""

    category: ObservationCategory = Field(..., description="Observation category")
    content: str = Field(..., description="The observation text")
    tags: list[str] = Field(
        default_factory=list, description="Inline tags from content"
    )
    context: str | None = Field(
        default=None, description="Additional context in parentheses"
    )
    line_number: int = Field(..., description="Line number for error reporting")
    decay_override: str | None = Field(default=None, description="Override to 'permanent' for decisions")
    auto_extracted: bool = Field(default=False, description="True if detected by parser/AI, False if user-written")


class Relation(BaseModel):
    """A semantic relation to another note."""

    relation_type: RelationType = Field(..., description="Type of relation")
    target: str = Field(..., description="Target note title/permalink")
    target_path: str | None = Field(
        default=None, description="Resolved path if wikilink had path"
    )
    context: str | None = Field(
        default=None, description="Additional context in parentheses"
    )
    line_number: int = Field(..., description="Line number for error reporting")


class Wikilink(BaseModel):
    """A wikilink reference."""

    target: str = Field(..., description="The linked note title")
    display_text: str | None = Field(
        default=None, description="Optional display text"
    )
    path: str | None = Field(
        default=None, description="Optional folder path"
    )
    anchor: str | None = Field(
        default=None, description="Optional heading anchor (e.g., #Section)"
    )
    block_ref: str | None = Field(
        default=None, description="Optional block reference (e.g., #^blockid)"
    )
    line_number: int = Field(..., description="Line number")
    column: int = Field(..., description="Character position in line")


class ParsedNote(BaseModel):
    """Fully parsed note structure."""

    frontmatter: Frontmatter = Field(..., description="Parsed frontmatter")
    observations: list[Observation] = Field(
        default_factory=list, description="Extracted observations"
    )
    relations: list[Relation] = Field(
        default_factory=list, description="Extracted relations"
    )
    wikilinks: list[Wikilink] = Field(
        default_factory=list, description="Extracted wikilinks"
    )
    raw_content: str = Field(..., description="Original content without frontmatter")
    headings: list[tuple[int, str]] = Field(
        default_factory=list, description="(level, text) pairs"
    )
    raw_frontmatter: str | None = Field(
        default=None,
        description="Original frontmatter text including delimiters for round-trip preservation",
    )
    frontmatter_modified: bool = Field(
        default=False,
        description="Flag indicating if frontmatter has been modified since parsing",
    )


class ProfileNote(BaseModel):
    """Synthesized user/project profile from memory analysis."""

    project: str = Field(..., description="Project this profile belongs to")
    static_facts: list[str] = Field(default_factory=list, description="Stable, persistent user facts and preferences")
    dynamic_patterns: list[str] = Field(default_factory=list, description="Recent behavioral patterns and focus areas")
    key_entities: dict[str, list[str]] = Field(default_factory=dict, description="Categorized key entities (tools, projects, people)")
    profile_version: int = Field(default=1, description="Profile version number, incremented on each synthesis")
    last_synthesized: datetime | None = Field(default=None, description="When profile was last synthesized")
    synthesis_note_count: int = Field(default=0, description="Number of notes analyzed in last synthesis")
