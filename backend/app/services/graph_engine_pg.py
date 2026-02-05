"""Postgres-backed graph engine service for knowledge graph operations.

This module provides a PostgresGraphEngine class that reads from the relations table
to provide graph traversal and query operations using SQLAlchemy async sessions.

It complements the file-based GraphEngine with database-backed operations
for Supabase/Postgres deployments.

Usage:
    from app.db import get_db
    from app.services.graph_engine_pg import PostgresGraphEngine

    async def get_backlinks(db: AsyncSession = Depends(get_db)):
        graph_engine = PostgresGraphEngine(db)
        backlinks = await graph_engine.get_backlinks(note_id, user_id)
        return backlinks
"""

from collections import deque
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.db_models import NoteModel, RelationModel
from app.schemas.graph import Graph, GraphEdge, GraphNode, RelationInfo


class PostgresGraphEngine:
    """Postgres-backed graph engine for knowledge graph operations.

    This class provides async methods for querying the knowledge graph stored
    in the relations table. It enforces user isolation through user_id checks
    by joining with the notes table.

    Attributes:
        session: SQLAlchemy async session for database operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            session: SQLAlchemy AsyncSession instance.
        """
        self._session = session

    async def get_backlinks(
        self, note_id: UUID, user_id: UUID
    ) -> list[RelationInfo]:
        """Get all notes that link TO the specified note (backlinks).

        Finds relations where the target_path matches the path of the given note.

        Args:
            note_id: UUID of the note to find backlinks for.
            user_id: UUID of the requesting user (for authorization).

        Returns:
            List of RelationInfo objects representing incoming links.
        """
        # First get the note's path
        note_stmt = select(NoteModel).where(
            NoteModel.id == str(note_id),
            NoteModel.user_id == str(user_id),
        )
        note_result = await self._session.execute(note_stmt)
        note = note_result.scalar_one_or_none()

        if note is None:
            return []

        # Find relations where target_path matches this note's path
        # and the source note belongs to the same user
        source_note = aliased(NoteModel)

        stmt = (
            select(
                RelationModel.source_id,
                source_note.path.label("source_path"),
                RelationModel.target_path,
                RelationModel.relation_type,
                RelationModel.context,
            )
            .join(source_note, RelationModel.source_id == source_note.id)
            .where(
                RelationModel.target_path == note.path,
                source_note.user_id == str(user_id),
            )
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            RelationInfo(
                source_id=UUID(row.source_id),
                source_path=row.source_path,
                target_path=row.target_path,
                relation_type=row.relation_type,
                context=row.context,
            )
            for row in rows
        ]

    async def get_outgoing_links(
        self, note_id: UUID, user_id: UUID
    ) -> list[RelationInfo]:
        """Get all notes that the specified note links TO (outgoing links).

        Finds relations where the source_id matches the given note.

        Args:
            note_id: UUID of the note to find outgoing links for.
            user_id: UUID of the requesting user (for authorization).

        Returns:
            List of RelationInfo objects representing outgoing links.
        """
        # Verify the note belongs to the user and get its path
        source_note = aliased(NoteModel)

        stmt = (
            select(
                RelationModel.source_id,
                source_note.path.label("source_path"),
                RelationModel.target_path,
                RelationModel.relation_type,
                RelationModel.context,
            )
            .join(source_note, RelationModel.source_id == source_note.id)
            .where(
                RelationModel.source_id == str(note_id),
                source_note.user_id == str(user_id),
            )
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            RelationInfo(
                source_id=UUID(row.source_id),
                source_path=row.source_path,
                target_path=row.target_path,
                relation_type=row.relation_type,
                context=row.context,
            )
            for row in rows
        ]

    async def get_tags(self, note_id: UUID, user_id: UUID) -> list[str]:
        """Get all tags associated with a note.

        Tags are stored as relations with relation_type='tag' and the tag name
        as the target_path.

        Args:
            note_id: UUID of the note to get tags for.
            user_id: UUID of the requesting user (for authorization).

        Returns:
            List of tag names (without the # prefix).
        """
        source_note = aliased(NoteModel)

        stmt = (
            select(RelationModel.target_path)
            .join(source_note, RelationModel.source_id == source_note.id)
            .where(
                RelationModel.source_id == str(note_id),
                RelationModel.relation_type == "tag",
                source_note.user_id == str(user_id),
            )
        )

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        # Remove # prefix if present
        return [tag.lstrip("#") for tag in rows]

    async def get_related_notes(
        self, note_id: UUID, user_id: UUID, max_depth: int = 2
    ) -> Graph:
        """Get a local subgraph of notes related to the specified note.

        Uses BFS traversal to find all notes within max_depth hops of the
        starting note. Includes both incoming and outgoing links.

        Args:
            note_id: UUID of the starting note.
            user_id: UUID of the requesting user (for authorization).
            max_depth: Maximum traversal depth (default 2).

        Returns:
            Graph object containing nodes and edges in the local subgraph.
        """
        # Verify the starting note exists and belongs to the user
        start_note_stmt = select(NoteModel).where(
            NoteModel.id == str(note_id),
            NoteModel.user_id == str(user_id),
        )
        start_note_result = await self._session.execute(start_note_stmt)
        start_note = start_note_result.scalar_one_or_none()

        if start_note is None:
            return Graph(nodes=[], edges=[])

        # BFS traversal
        # Track visited note IDs and their paths
        visited_ids: set[str] = {str(note_id)}
        visited_paths: set[str] = {start_note.path}

        # Map path -> note_id for quick lookups
        path_to_id: dict[str, str] = {start_note.path: str(note_id)}

        # Map note_id -> GraphNode
        nodes_map: dict[str, GraphNode] = {
            str(note_id): GraphNode(
                id=UUID(start_note.id),
                path=start_note.path,
                title=start_note.title,
            )
        }

        # Edges to include in the graph (source_id, target_id, relation_type)
        edges_set: set[tuple[str, str, str]] = set()

        # BFS queue: (note_id, note_path, current_depth)
        queue: deque[tuple[str, str, int]] = deque(
            [(str(note_id), start_note.path, 0)]
        )

        while queue:
            current_id, current_path, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Get outgoing relations from this note
            outgoing_stmt = (
                select(
                    RelationModel.target_path,
                    RelationModel.relation_type,
                )
                .where(RelationModel.source_id == current_id)
            )
            outgoing_result = await self._session.execute(outgoing_stmt)
            outgoing_relations = outgoing_result.all()

            for row in outgoing_relations:
                target_path = row.target_path
                relation_type = row.relation_type

                # Skip tags for graph traversal (they're not notes)
                if relation_type == "tag":
                    continue

                # Find the target note by path (must belong to the same user)
                if target_path not in visited_paths:
                    target_note_stmt = select(NoteModel).where(
                        NoteModel.path == target_path,
                        NoteModel.user_id == str(user_id),
                    )
                    target_note_result = await self._session.execute(target_note_stmt)
                    target_note = target_note_result.scalar_one_or_none()

                    if target_note is not None:
                        target_note_id = target_note.id
                        visited_ids.add(target_note_id)
                        visited_paths.add(target_path)
                        path_to_id[target_path] = target_note_id
                        nodes_map[target_note_id] = GraphNode(
                            id=UUID(target_note_id),
                            path=target_note.path,
                            title=target_note.title,
                        )
                        queue.append((target_note_id, target_path, depth + 1))

                # Add edge if we have both endpoints
                if target_path in path_to_id:
                    target_note_id = path_to_id[target_path]
                    edges_set.add((current_id, target_note_id, relation_type))

            # Get incoming relations to this note (backlinks)
            # Find relations where target_path matches current note's path
            incoming_stmt = (
                select(
                    RelationModel.source_id,
                    RelationModel.relation_type,
                )
                .where(RelationModel.target_path == current_path)
            )
            incoming_result = await self._session.execute(incoming_stmt)
            incoming_relations = incoming_result.all()

            for row in incoming_relations:
                source_id = row.source_id
                relation_type = row.relation_type

                # Skip tags
                if relation_type == "tag":
                    continue

                if source_id not in visited_ids:
                    # Verify source note belongs to user
                    source_note_stmt = select(NoteModel).where(
                        NoteModel.id == source_id,
                        NoteModel.user_id == str(user_id),
                    )
                    source_note_result = await self._session.execute(source_note_stmt)
                    source_note = source_note_result.scalar_one_or_none()

                    if source_note is not None:
                        visited_ids.add(source_id)
                        visited_paths.add(source_note.path)
                        path_to_id[source_note.path] = source_id
                        nodes_map[source_id] = GraphNode(
                            id=UUID(source_id),
                            path=source_note.path,
                            title=source_note.title,
                        )
                        queue.append((source_id, source_note.path, depth + 1))

                # Add edge if we have both endpoints
                if source_id in visited_ids:
                    edges_set.add((source_id, current_id, relation_type))

        # Build final graph
        nodes = list(nodes_map.values())
        edges = [
            GraphEdge(
                source_id=UUID(source_id),
                target_id=UUID(target_id),
                relation_type=relation_type,
            )
            for source_id, target_id, relation_type in edges_set
        ]

        return Graph(nodes=nodes, edges=edges)

    async def get_notes_by_tag(
        self, tag: str, user_id: UUID, limit: int = 100
    ) -> list[GraphNode]:
        """Get all notes that have a specific tag.

        Args:
            tag: Tag name (with or without # prefix).
            user_id: UUID of the requesting user.
            limit: Maximum number of notes to return.

        Returns:
            List of GraphNode objects for notes with the specified tag.
        """
        # Normalize tag (remove # if present)
        tag_normalized = tag.lstrip("#")

        source_note = aliased(NoteModel)

        stmt = (
            select(source_note)
            .join(RelationModel, RelationModel.source_id == source_note.id)
            .where(
                RelationModel.relation_type == "tag",
                RelationModel.target_path.in_([f"#{tag_normalized}", tag_normalized]),
                source_note.user_id == str(user_id),
            )
            .distinct()
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        notes = result.scalars().all()

        return [
            GraphNode(
                id=UUID(note.id),
                path=note.path,
                title=note.title,
            )
            for note in notes
        ]

    async def get_all_tags(self, user_id: UUID) -> list[tuple[str, int]]:
        """Get all tags used by a user with their counts.

        Args:
            user_id: UUID of the requesting user.

        Returns:
            List of (tag_name, count) tuples sorted by count descending.
        """
        from sqlalchemy import func

        source_note = aliased(NoteModel)

        stmt = (
            select(
                RelationModel.target_path,
                func.count(RelationModel.id).label("count"),
            )
            .join(source_note, RelationModel.source_id == source_note.id)
            .where(
                RelationModel.relation_type == "tag",
                source_note.user_id == str(user_id),
            )
            .group_by(RelationModel.target_path)
            .order_by(func.count(RelationModel.id).desc())
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        return [(row.target_path.lstrip("#"), row.count) for row in rows]
