"""Postgres-backed vault manager service for database-driven note storage.

This module provides a PostgresVaultManager class that implements note CRUD operations
using SQLAlchemy async sessions against a Postgres database (Supabase).

It replaces file-based .md storage with database records while maintaining
the vault-like path structure for Obsidian compatibility.

Usage:
    from app.db import get_db
    from app.services.vault_manager_pg import PostgresVaultManager

    async def get_notes(db: AsyncSession = Depends(get_db)):
        vault_manager = PostgresVaultManager(db)
        notes = await vault_manager.list_notes(user_id=current_user.id)
        return notes
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import NoteModel
from app.schemas.notes import Note, NoteCreate, NoteListItem, NoteUpdate
from app.services.exceptions import (
    DuplicatePathError,
    NoteNotFoundError,
    UnauthorizedError,
)


class PostgresVaultManager:
    """Postgres-backed vault manager for note CRUD operations.

    This class provides async methods for creating, reading, updating, and deleting
    notes stored in a Postgres database. It enforces user isolation through user_id
    checks on all operations.

    Attributes:
        session: SQLAlchemy async session for database operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            session: SQLAlchemy AsyncSession instance.
        """
        self._session = session

    def _model_to_note(self, model: NoteModel) -> Note:
        """Convert a NoteModel to a Note schema.

        Args:
            model: NoteModel ORM instance.

        Returns:
            Note pydantic schema.
        """
        return Note(
            id=UUID(model.id),
            path=model.path,
            title=model.title,
            content=model.content,
            frontmatter=model.frontmatter if model.frontmatter else {},
            created_at=model.created_at,
            updated_at=model.updated_at,
            user_id=UUID(model.user_id) if model.user_id else None,
        )

    def _model_to_list_item(self, model: NoteModel) -> NoteListItem:
        """Convert a NoteModel to a NoteListItem schema.

        Args:
            model: NoteModel ORM instance.

        Returns:
            NoteListItem pydantic schema.
        """
        return NoteListItem(
            id=UUID(model.id),
            path=model.path,
            title=model.title,
            updated_at=model.updated_at,
            created_at=model.created_at,
        )

    async def get_note(self, path: str, user_id: UUID) -> Note:
        """Get a note by its path.

        Args:
            path: Vault-style path (e.g., "projects/my-project/design.md").
            user_id: UUID of the requesting user.

        Returns:
            Note schema with full note data.

        Raises:
            NoteNotFoundError: If no note exists at the given path for this user.
        """
        stmt = select(NoteModel).where(
            NoteModel.path == path,
            NoteModel.user_id == str(user_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise NoteNotFoundError(path, by_field="path")

        return self._model_to_note(model)

    async def get_note_by_id(self, note_id: UUID, user_id: UUID) -> Note:
        """Get a note by its unique ID.

        Args:
            note_id: UUID of the note.
            user_id: UUID of the requesting user.

        Returns:
            Note schema with full note data.

        Raises:
            NoteNotFoundError: If no note exists with the given ID.
            UnauthorizedError: If the note exists but belongs to a different user.
        """
        stmt = select(NoteModel).where(NoteModel.id == str(note_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise NoteNotFoundError(str(note_id), by_field="id")

        # Check user ownership
        if model.user_id != str(user_id):
            raise UnauthorizedError(str(note_id), str(user_id))

        return self._model_to_note(model)

    async def create_note(self, note: NoteCreate, user_id: UUID) -> Note:
        """Create a new note.

        Args:
            note: NoteCreate schema with note data.
            user_id: UUID of the creating user.

        Returns:
            Note schema with the created note including generated ID and timestamps.

        Raises:
            DuplicatePathError: If a note already exists at the given path for this user.
        """
        # Check for existing note at this path for this user
        existing_stmt = select(NoteModel).where(
            NoteModel.path == note.path,
            NoteModel.user_id == str(user_id),
        )
        existing_result = await self._session.execute(existing_stmt)
        if existing_result.scalar_one_or_none() is not None:
            raise DuplicatePathError(note.path)

        now = datetime.now(timezone.utc)
        model = NoteModel(
            id=str(uuid4()),
            path=note.path,
            title=note.title,
            content=note.content,
            frontmatter=note.frontmatter,
            created_at=now,
            updated_at=now,
            user_id=str(user_id),
        )

        self._session.add(model)

        try:
            await self._session.flush()
        except IntegrityError as e:
            await self._session.rollback()
            # Handle race condition where another request created the same path
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise DuplicatePathError(note.path) from e
            raise

        await self._session.refresh(model)
        return self._model_to_note(model)

    async def update_note(
        self, note_id: UUID, note: NoteUpdate, user_id: UUID
    ) -> Note:
        """Update an existing note.

        Only provided fields (non-None) will be updated.

        Args:
            note_id: UUID of the note to update.
            note: NoteUpdate schema with fields to update.
            user_id: UUID of the requesting user.

        Returns:
            Note schema with the updated note data.

        Raises:
            NoteNotFoundError: If no note exists with the given ID.
            UnauthorizedError: If the note exists but belongs to a different user.
            DuplicatePathError: If updating the path would conflict with an existing note.
        """
        # Fetch the note (will raise appropriate errors)
        stmt = select(NoteModel).where(NoteModel.id == str(note_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise NoteNotFoundError(str(note_id), by_field="id")

        if model.user_id != str(user_id):
            raise UnauthorizedError(str(note_id), str(user_id))

        # Check for path conflict if path is being updated
        if note.path is not None and note.path != model.path:
            path_check_stmt = select(NoteModel).where(
                NoteModel.path == note.path,
                NoteModel.user_id == str(user_id),
                NoteModel.id != str(note_id),
            )
            path_check_result = await self._session.execute(path_check_stmt)
            if path_check_result.scalar_one_or_none() is not None:
                raise DuplicatePathError(note.path)

        # Apply updates
        if note.path is not None:
            model.path = note.path
        if note.title is not None:
            model.title = note.title
        if note.content is not None:
            model.content = note.content
        if note.frontmatter is not None:
            model.frontmatter = note.frontmatter

        model.updated_at = datetime.now(timezone.utc)

        try:
            await self._session.flush()
        except IntegrityError as e:
            await self._session.rollback()
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise DuplicatePathError(note.path or model.path) from e
            raise

        await self._session.refresh(model)
        return self._model_to_note(model)

    async def delete_note(self, note_id: UUID, user_id: UUID) -> None:
        """Delete a note.

        Args:
            note_id: UUID of the note to delete.
            user_id: UUID of the requesting user.

        Raises:
            NoteNotFoundError: If no note exists with the given ID.
            UnauthorizedError: If the note exists but belongs to a different user.
        """
        stmt = select(NoteModel).where(NoteModel.id == str(note_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise NoteNotFoundError(str(note_id), by_field="id")

        if model.user_id != str(user_id):
            raise UnauthorizedError(str(note_id), str(user_id))

        await self._session.delete(model)
        await self._session.flush()

    async def list_notes(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NoteListItem]:
        """List notes for a user with pagination.

        Notes are ordered by updated_at descending (most recent first).

        Args:
            user_id: UUID of the requesting user.
            limit: Maximum number of notes to return (default 100, max 1000).
            offset: Number of notes to skip for pagination (default 0).

        Returns:
            List of NoteListItem schemas.
        """
        # Clamp limit to reasonable bounds
        limit = min(max(1, limit), 1000)
        offset = max(0, offset)

        stmt = (
            select(NoteModel)
            .where(NoteModel.user_id == str(user_id))
            .order_by(NoteModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._model_to_list_item(model) for model in models]

    async def count_notes(self, user_id: UUID) -> int:
        """Count total notes for a user.

        Args:
            user_id: UUID of the requesting user.

        Returns:
            Total number of notes owned by the user.
        """
        from sqlalchemy import func

        stmt = select(func.count(NoteModel.id)).where(
            NoteModel.user_id == str(user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def search_notes_by_path_prefix(
        self,
        user_id: UUID,
        path_prefix: str,
        limit: int = 100,
    ) -> list[NoteListItem]:
        """Search notes by path prefix (folder).

        Useful for listing notes within a specific folder/project.

        Args:
            user_id: UUID of the requesting user.
            path_prefix: Path prefix to match (e.g., "projects/my-project/").
            limit: Maximum number of notes to return.

        Returns:
            List of NoteListItem schemas matching the prefix.
        """
        limit = min(max(1, limit), 1000)

        stmt = (
            select(NoteModel)
            .where(
                NoteModel.user_id == str(user_id),
                NoteModel.path.like(f"{path_prefix}%"),
            )
            .order_by(NoteModel.updated_at.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._model_to_list_item(model) for model in models]
