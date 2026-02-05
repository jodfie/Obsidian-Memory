"""SQLAlchemy ORM models for dual-mode SQLite/Postgres database.

These models match the Postgres schema defined in the Supabase migration plan
and work with both SQLite (local development) and Postgres (production).

Schema follows: docs/plans/2026-02-05-supabase-electric-migration-design.md
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Type adapter for JSON that works with both SQLite and Postgres
# SQLite stores JSON as TEXT, Postgres uses native JSONB
def json_column():
    """Create a JSON column that works with both SQLite and Postgres.

    Returns:
        A mapped_column configured for JSON storage.
    """
    # SQLAlchemy will automatically use JSON type which maps to:
    # - JSONB on Postgres
    # - TEXT with JSON serialization on SQLite
    from sqlalchemy import JSON

    return mapped_column(JSON, default=dict, nullable=False)


class NoteModel(Base):
    """SQLAlchemy model for notes.

    This replaces the file-based .md storage with database records.
    The content column stores the markdown body, while frontmatter
    metadata is stored as JSONB for flexible querying.

    Attributes:
        id: UUID primary key
        path: Unique path mimicking vault structure (e.g., "projects/my-project/design.md")
        title: Note title extracted from frontmatter
        content: Markdown content body (without frontmatter)
        frontmatter: YAML frontmatter stored as JSON for querying
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        user_id: User UUID for multi-tenancy (Supabase Auth integration)
    """

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID primary key",
    )
    path: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
        index=True,
        comment="Vault-style path (e.g., 'projects/my-project/design.md')",
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Note title from frontmatter",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="Markdown content body",
    )
    frontmatter: Mapped[dict] = json_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        comment="Creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        comment="Last modification timestamp",
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="User UUID for multi-tenancy (nullable for local SQLite mode)",
    )

    # Relationships
    relations_as_source: Mapped[list["RelationModel"]] = relationship(
        "RelationModel",
        back_populates="source_note",
        cascade="all, delete-orphan",
        foreign_keys="RelationModel.source_id",
    )

    # Table-level indexes for full-text search (Postgres-specific, ignored by SQLite)
    __table_args__ = (
        Index(
            "ix_notes_updated_at_desc",
            updated_at.desc(),
        ),
        {"comment": "Core notes table replacing .md file storage"},
    )

    def __repr__(self) -> str:
        return f"<NoteModel(id={self.id!r}, path={self.path!r}, title={self.title!r})>"


class RelationModel(Base):
    """SQLAlchemy model for note relations.

    Stores extracted relations between notes including:
    - Wikilinks [[target]]
    - Tags #tag
    - Semantic relations (depends_on, enables, etc.)

    Attributes:
        id: UUID primary key
        source_id: Foreign key to source note
        target_path: Path of the linked/related note
        relation_type: Type of relation (wikilink, tag, depends_on, etc.)
        context: Surrounding text for context
    """

    __tablename__ = "relations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID primary key",
    )
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to source note",
    )
    target_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        comment="Path of the linked/related note",
    )
    relation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: wikilink, tag, depends_on, enables, related_to, etc.",
    )
    context: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Surrounding text for context",
    )

    # Relationships
    source_note: Mapped["NoteModel"] = relationship(
        "NoteModel",
        back_populates="relations_as_source",
        foreign_keys=[source_id],
    )

    __table_args__ = (
        Index("ix_relations_source_target", source_id, target_path),
        {"comment": "Extracted relations between notes (wikilinks, tags, semantic)"},
    )

    def __repr__(self) -> str:
        return f"<RelationModel(id={self.id!r}, type={self.relation_type!r}, target={self.target_path!r})>"


class SessionModel(Base):
    """SQLAlchemy model for Claude Code sessions.

    Tracks Claude Code interaction sessions including:
    - Session metadata (project, start/end times)
    - Events within the session
    - AI-generated summaries

    Attributes:
        id: UUID primary key
        project: Associated project identifier
        started_at: Session start timestamp
        ended_at: Session end timestamp (null if active)
        summary: AI-generated session summary
        events: JSON array of session events
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID primary key",
    )
    project: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="Associated project identifier",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        index=True,
        comment="Session start timestamp",
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Session end timestamp (null if active)",
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated session summary",
    )
    events: Mapped[list] = mapped_column(
        JSONB().with_variant(Text, "sqlite"),
        default=list,
        nullable=False,
        comment="JSON array of session events",
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="User UUID for multi-tenancy (nullable for local SQLite mode)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        comment="Session status: active, completed, cancelled",
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB().with_variant(Text, "sqlite"),
        nullable=True,
        comment="Additional session metadata",
    )

    __table_args__ = (
        Index("ix_sessions_started_at_desc", started_at.desc()),
        {"comment": "Claude Code interaction sessions"},
    )

    def __repr__(self) -> str:
        return f"<SessionModel(id={self.id!r}, project={self.project!r}, status={self.status!r})>"


# Export all models for easy importing
__all__ = [
    "Base",
    "NoteModel",
    "RelationModel",
    "SessionModel",
]
