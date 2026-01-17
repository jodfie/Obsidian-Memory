"""Full-text search index using SQLite FTS5."""

import hashlib
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from app.models.note import (
    Observation,
    ObservationCategory,
    Relation,
    RelationType,
    Wikilink,
)
from app.models.search import (
    IndexedNote,
    SearchQuery,
    SearchResult,
    SearchResults,
    SortOrder,
)


def compute_file_hash(content: str) -> str:
    """Compute hash for change detection."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


class SearchIndex:
    """Full-text search index using SQLite FTS5."""

    def __init__(self, db_path: Path) -> None:
        """Initialize with database path."""
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db = await aiosqlite.connect(str(self.db_path))
        self.db.row_factory = aiosqlite.Row

        # Enable WAL mode for concurrent access
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA synchronous=NORMAL")

        # Create schema
        await self._create_schema()
        await self.db.commit()

    async def _create_schema(self) -> None:
        """Create database schema."""
        # Notes metadata table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vault_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                permalink TEXT UNIQUE,
                title TEXT NOT NULL,
                note_type TEXT DEFAULT 'note',
                project TEXT,
                created_at TEXT,
                updated_at TEXT,
                indexed_at TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                UNIQUE(vault_name, relative_path)
            )
        """)

        # Create indexes
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_vault ON notes(vault_name)"
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_project ON notes(project)"
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(note_type)"
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_permalink ON notes(permalink)"
        )

        # Full-text search index
        await self.db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                title,
                content,
                tags,
                observations,
                content='notes',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)

        # Tags table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS note_tags (
                note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                tag TEXT NOT NULL,
                PRIMARY KEY (note_id, tag)
            )
        """)
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_tags_tag ON note_tags(tag)"
        )

        # Observations table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT,
                line_number INTEGER
            )
        """)
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_note ON observations(note_id)"
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_category ON observations(category)"
        )

        # Relations table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                relation_type TEXT NOT NULL,
                target_title TEXT NOT NULL,
                target_note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
                context TEXT
            )
        """)
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_note_id)"
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_note_id)"
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type)"
        )

        # Wikilinks table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS wikilinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                target_title TEXT NOT NULL,
                target_note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
                display_text TEXT
            )
        """)
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_wikilinks_source ON wikilinks(source_note_id)"
        )
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_wikilinks_target ON wikilinks(target_note_id)"
        )

        # FTS triggers for keeping index in sync
        await self.db.execute("""
            CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, title, content, tags, observations)
                VALUES (new.id, new.title, '', '', '');
            END
        """)

        await self.db.execute("""
            CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
                VALUES('delete', old.id, old.title, '', '', '');
            END
        """)

        await self.db.execute("""
            CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
                VALUES('delete', old.id, old.title, '', '', '');
                INSERT INTO notes_fts(rowid, title, content, tags, observations)
                VALUES (new.id, new.title, '', '', '');
            END
        """)

    async def close(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()
            self.db = None

    async def __aenter__(self) -> "SearchIndex":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # Indexing Operations

    async def index_note(self, note: IndexedNote) -> int:
        """
        Index or update a note.

        Returns the note_id.
        """
        if not self.db:
            raise RuntimeError("Database not initialized")

        indexed_at = datetime.utcnow().isoformat()
        created_at_str = (
            note.created_at.isoformat() if note.created_at else None
        )
        updated_at_str = (
            note.updated_at.isoformat() if note.updated_at else None
        )

        # Check if note exists
        cursor = await self.db.execute(
            """
            SELECT id FROM notes
            WHERE vault_name = ? AND relative_path = ?
            """,
            (note.vault_name, note.relative_path),
        )
        row = await cursor.fetchone()

        if row:
            # Update existing note
            note_id = row['id']
            await self.db.execute(
                """
                UPDATE notes SET
                    permalink = ?,
                    title = ?,
                    note_type = ?,
                    project = ?,
                    created_at = ?,
                    updated_at = ?,
                    indexed_at = ?,
                    file_hash = ?
                WHERE id = ?
                """,
                (
                    note.permalink,
                    note.title,
                    note.note_type,
                    note.project,
                    created_at_str,
                    updated_at_str,
                    indexed_at,
                    note.file_hash,
                    note_id,
                ),
            )
        else:
            # Insert new note
            cursor = await self.db.execute(
                """
                INSERT INTO notes (
                    vault_name, relative_path, permalink, title, note_type,
                    project, created_at, updated_at, indexed_at, file_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.vault_name,
                    note.relative_path,
                    note.permalink,
                    note.title,
                    note.note_type,
                    note.project,
                    created_at_str,
                    updated_at_str,
                    indexed_at,
                    note.file_hash,
                ),
            )
            note_id = cursor.lastrowid

        # Update FTS index
        tags_str = ' '.join(note.tags)
        observations_str = ' '.join(
            [obs.content for obs in note.observations]
        )

        # Delete old FTS entry
        await self.db.execute(
            """
            INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
            VALUES('delete', ?, '', '', '', '')
            """,
            (note_id,),
        )

        # Insert new FTS entry
        await self.db.execute(
            """
            INSERT INTO notes_fts(rowid, title, content, tags, observations)
            VALUES (?, ?, ?, ?, ?)
            """,
            (note_id, note.title, note.content, tags_str, observations_str),
        )

        # Update tags
        await self.db.execute(
            "DELETE FROM note_tags WHERE note_id = ?", (note_id,)
        )
        for tag in note.tags:
            await self.db.execute(
                "INSERT INTO note_tags(note_id, tag) VALUES (?, ?)",
                (note_id, tag),
            )

        # Update observations
        await self.db.execute(
            "DELETE FROM observations WHERE note_id = ?", (note_id,)
        )
        for obs in note.observations:
            await self.db.execute(
                """
                INSERT INTO observations(note_id, category, content, context, line_number)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    obs.category.value,
                    obs.content,
                    obs.context,
                    obs.line_number,
                ),
            )

        # Update relations (resolve targets)
        await self.db.execute(
            "DELETE FROM relations WHERE source_note_id = ?", (note_id,)
        )
        for rel in note.relations:
            target_note_id = await self.resolve_wikilink(
                rel.target, note.vault_name
            )
            await self.db.execute(
                """
                INSERT INTO relations(
                    source_note_id, relation_type, target_title, target_note_id, context
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    rel.relation_type.value,
                    rel.target,
                    target_note_id,
                    rel.context,
                ),
            )

        # Update wikilinks (resolve targets)
        await self.db.execute(
            "DELETE FROM wikilinks WHERE source_note_id = ?", (note_id,)
        )
        for wl in note.wikilinks:
            target_note_id = await self.resolve_wikilink(
                wl.target, note.vault_name
            )
            await self.db.execute(
                """
                INSERT INTO wikilinks(source_note_id, target_title, target_note_id, display_text)
                VALUES (?, ?, ?, ?)
                """,
                (note_id, wl.target, target_note_id, wl.display_text),
            )

        await self.db.commit()
        return note_id

    async def remove_note(
        self, vault_name: str, relative_path: str
    ) -> bool:
        """Remove a note from the index."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        cursor = await self.db.execute(
            """
            DELETE FROM notes
            WHERE vault_name = ? AND relative_path = ?
            """,
            (vault_name, relative_path),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def needs_reindex(
        self, vault_name: str, relative_path: str, file_hash: str
    ) -> bool:
        """Check if a note needs reindexing based on file hash."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        cursor = await self.db.execute(
            """
            SELECT file_hash FROM notes
            WHERE vault_name = ? AND relative_path = ?
            """,
            (vault_name, relative_path),
        )
        row = await cursor.fetchone()
        if not row:
            return True
        return row['file_hash'] != file_hash

    # Search Operations

    def _build_fts_query(self, query: SearchQuery) -> str:
        """Build FTS5 MATCH clause from search query."""

        def escape_fts(term: str) -> str:
            """Escape FTS5 special characters."""
            if any(c in term for c in '+-*"(){}[]^~:'):
                return f'"{term}"'
            return term

        terms = []
        for word in query.query.split():
            if word.upper() in ('AND', 'OR', 'NOT'):
                terms.append(word.upper())
            elif word.startswith('"') and word.endswith('"'):
                terms.append(word)  # Already quoted phrase
            elif ':' in word:
                # Column-specific search
                col, term = word.split(':', 1)
                if col in ('title', 'content', 'tags', 'observations'):
                    terms.append(f'{col}:{escape_fts(term)}')
            else:
                terms.append(escape_fts(word))

        return ' '.join(terms)

    async def _generate_snippet(
        self, note_id: int, query: str, max_length: int = 200
    ) -> str:
        """Generate highlighted snippet for search result."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        try:
            cursor = await self.db.execute(
                """
                SELECT snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32)
                FROM notes_fts
                WHERE rowid = ? AND notes_fts MATCH ?
                """,
                (note_id, query),
            )
            row = await cursor.fetchone()
            if row and row[0]:
                snippet = row[0]
                # Remove HTML tags for plain text
                snippet = re.sub(r'<[^>]+>', '', snippet)
                if len(snippet) > max_length:
                    snippet = snippet[:max_length] + '...'
                return snippet
        except Exception:
            pass
        return ""

    async def search(self, query: SearchQuery) -> SearchResults:
        """Execute a search query."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        start_time = time.time()

        # Build WHERE clause
        where_parts = []
        params: list[Any] = []

        # FTS query
        fts_query = self._build_fts_query(query)
        if fts_query:
            where_parts.append("notes_fts MATCH ?")
            params.append(fts_query)

        # Filters
        if query.vault:
            where_parts.append("n.vault_name = ?")
            params.append(query.vault)

        if query.project:
            where_parts.append("n.project = ?")
            params.append(query.project)

        if query.note_type:
            where_parts.append("n.note_type = ?")
            params.append(query.note_type)

        if query.tags:
            where_parts.append(
                f"""
                n.id IN (
                    SELECT note_id FROM note_tags
                    WHERE tag IN ({','.join('?' * len(query.tags))})
                    GROUP BY note_id
                    HAVING COUNT(DISTINCT tag) = ?
                )
                """
            )
            params.extend(query.tags)
            params.append(len(query.tags))

        if query.tags_any:
            where_parts.append(
                f"n.id IN (SELECT note_id FROM note_tags WHERE tag IN ({','.join('?' * len(query.tags_any))}))"
            )
            params.extend(query.tags_any)

        if query.observation_category:
            where_parts.append(
                """
                n.id IN (
                    SELECT note_id FROM observations WHERE category = ?
                )
                """
            )
            params.append(query.observation_category)

        if query.created_after:
            where_parts.append("n.created_at >= ?")
            params.append(query.created_after.isoformat())

        if query.created_before:
            where_parts.append("n.created_at <= ?")
            params.append(query.created_before.isoformat())

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        # Build ORDER BY
        order_by = "bm25(notes_fts) ASC"  # Lower is better
        if query.sort == SortOrder.CREATED_DESC:
            order_by = "n.created_at DESC"
        elif query.sort == SortOrder.CREATED_ASC:
            order_by = "n.created_at ASC"
        elif query.sort == SortOrder.UPDATED_DESC:
            order_by = "n.updated_at DESC"
        elif query.sort == SortOrder.UPDATED_ASC:
            order_by = "n.updated_at ASC"
        elif query.sort == SortOrder.TITLE_ASC:
            order_by = "n.title ASC"

        # Get total count
        count_cursor = await self.db.execute(
            f"""
            SELECT COUNT(DISTINCT n.id) as total
            FROM notes n
            INNER JOIN notes_fts ON notes_fts.rowid = n.id
            WHERE {where_clause}
            """,
            params,
        )
        count_row = await count_cursor.fetchone()
        total_count = count_row['total'] if count_row else 0

        # Get results
        search_cursor = await self.db.execute(
            f"""
            SELECT DISTINCT
                n.id, n.vault_name, n.relative_path, n.permalink,
                n.title, n.note_type, n.project,
                n.created_at, n.updated_at,
                bm25(notes_fts) as score
            FROM notes n
            INNER JOIN notes_fts ON notes_fts.rowid = n.id
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [*params, query.limit, query.offset],
        )

        results: list[SearchResult] = []
        async for row in search_cursor:
            # Get tags
            tags_cursor = await self.db.execute(
                "SELECT tag FROM note_tags WHERE note_id = ?", (row['id'],)
            )
            tags = [tag_row['tag'] async for tag_row in tags_cursor]

            # Generate snippet
            snippet = await self._generate_snippet(row['id'], fts_query)

            # Parse dates
            created_at = None
            if row['created_at']:
                try:
                    created_at = datetime.fromisoformat(row['created_at'])
                except ValueError:
                    pass

            updated_at = None
            if row['updated_at']:
                try:
                    updated_at = datetime.fromisoformat(row['updated_at'])
                except ValueError:
                    pass

            results.append(
                SearchResult(
                    note_id=row['id'],
                    vault_name=row['vault_name'],
                    relative_path=row['relative_path'],
                    permalink=row['permalink'],
                    title=row['title'],
                    note_type=row['note_type'],
                    project=row['project'],
                    snippet=snippet,
                    score=float(row['score']),
                    created_at=created_at,
                    updated_at=updated_at,
                    tags=tags,
                )
            )

        took_ms = (time.time() - start_time) * 1000

        return SearchResults(
            results=results,
            total_count=total_count,
            query=query.query,
            took_ms=took_ms,
        )

    async def search_similar(
        self, note_id: int, limit: int = 10
    ) -> list[SearchResult]:
        """Find notes similar to a given note."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        # Get note content
        cursor = await self.db.execute(
            """
            SELECT title, content FROM notes_fts WHERE rowid = ?
            """,
            (note_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return []

        # Build query from title and content
        title_words = row['title'].split()[:5]  # Use first 5 words
        query_str = ' OR '.join(title_words)

        # Search for similar notes
        search_query = SearchQuery(query=query_str, limit=limit + 1)
        results = await self.search(search_query)

        # Filter out the original note
        similar = [r for r in results.results if r.note_id != note_id]
        return similar[:limit]

    # Query Helpers

    async def get_note_by_id(self, note_id: int) -> IndexedNote | None:
        """Get full indexed note by ID."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        cursor = await self.db.execute(
            """
            SELECT * FROM notes WHERE id = ?
            """,
            (note_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Get tags
        tags_cursor = await self.db.execute(
            "SELECT tag FROM note_tags WHERE note_id = ?", (note_id,)
        )
        tags = [tag_row['tag'] async for tag_row in tags_cursor]

        # Get observations
        obs_cursor = await self.db.execute(
            "SELECT * FROM observations WHERE note_id = ?", (note_id,)
        )
        observations = []
        async for obs_row in obs_cursor:
            observations.append(
                Observation(
                    category=ObservationCategory(obs_row['category']),
                    content=obs_row['content'],
                    context=obs_row['context'],
                    line_number=obs_row['line_number'],
                    tags=[],
                )
            )

        # Get relations
        rel_cursor = await self.db.execute(
            "SELECT * FROM relations WHERE source_note_id = ?", (note_id,)
        )
        relations = []
        async for rel_row in rel_cursor:
            relations.append(
                Relation(
                    relation_type=RelationType(rel_row['relation_type']),
                    target=rel_row['target_title'],
                    target_path=None,
                    context=rel_row['context'],
                    line_number=0,
                )
            )

        # Get wikilinks
        wl_cursor = await self.db.execute(
            "SELECT * FROM wikilinks WHERE source_note_id = ?", (note_id,)
        )
        wikilinks = []
        async for wl_row in wl_cursor:
            wikilinks.append(
                Wikilink(
                    target=wl_row['target_title'],
                    display_text=wl_row['display_text'],
                    path=None,
                    line_number=0,
                    column=0,
                )
            )

        # Note: FTS5 doesn't store full content, only indexed tokens
        # Content should be fetched from VaultManager if needed
        content = ""

        # Parse dates
        created_at = None
        if row['created_at']:
            try:
                created_at = datetime.fromisoformat(row['created_at'])
            except ValueError:
                pass

        updated_at = None
        if row['updated_at']:
            try:
                updated_at = datetime.fromisoformat(row['updated_at'])
            except ValueError:
                pass

        return IndexedNote(
            vault_name=row['vault_name'],
            relative_path=row['relative_path'],
            permalink=row['permalink'],
            title=row['title'],
            note_type=row['note_type'],
            project=row['project'],
            content=content,
            tags=tags,
            observations=observations,
            relations=relations,
            wikilinks=wikilinks,
            created_at=created_at,
            updated_at=updated_at,
            file_hash=row['file_hash'],
        )

    async def get_note_by_permalink(
        self, permalink: str
    ) -> IndexedNote | None:
        """Get note by permalink."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        cursor = await self.db.execute(
            "SELECT id FROM notes WHERE permalink = ?", (permalink,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return await self.get_note_by_id(row['id'])

    async def get_note_by_path(
        self, vault_name: str, relative_path: str
    ) -> IndexedNote | None:
        """Get note by vault and path."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        cursor = await self.db.execute(
            """
            SELECT id FROM notes
            WHERE vault_name = ? AND relative_path = ?
            """,
            (vault_name, relative_path),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return await self.get_note_by_id(row['id'])

    async def resolve_wikilink(
        self, target_title: str, from_vault: str | None = None
    ) -> int | None:
        """Resolve a wikilink target to a note_id."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        # 1. Exact title match in same vault
        if from_vault:
            cursor = await self.db.execute(
                """
                SELECT id FROM notes
                WHERE vault_name = ? AND title = ?
                LIMIT 1
                """,
                (from_vault, target_title),
            )
            row = await cursor.fetchone()
            if row:
                return row['id']

        # 2. Exact permalink match
        cursor = await self.db.execute(
            "SELECT id FROM notes WHERE permalink = ? LIMIT 1",
            (target_title,),
        )
        row = await cursor.fetchone()
        if row:
            return row['id']

        # 3. Exact title match in any vault
        cursor = await self.db.execute(
            "SELECT id FROM notes WHERE title = ? LIMIT 1", (target_title,)
        )
        row = await cursor.fetchone()
        if row:
            return row['id']

        # 4. Case-insensitive title match
        cursor = await self.db.execute(
            "SELECT id FROM notes WHERE LOWER(title) = LOWER(?) LIMIT 1",
            (target_title,),
        )
        row = await cursor.fetchone()
        if row:
            return row['id']

        return None

    # Aggregation Queries

    async def list_tags(
        self, vault: str | None = None, project: str | None = None
    ) -> list[tuple[str, int]]:
        """List all tags with counts."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        query = """
            SELECT nt.tag, COUNT(*) as count
            FROM note_tags nt
            INNER JOIN notes n ON n.id = nt.note_id
            WHERE 1=1
        """
        params: list[Any] = []

        if vault:
            query += " AND n.vault_name = ?"
            params.append(vault)

        if project:
            query += " AND n.project = ?"
            params.append(project)

        query += " GROUP BY nt.tag ORDER BY count DESC"

        cursor = await self.db.execute(query, params)
        return [(row['tag'], row['count']) async for row in cursor]

    async def list_projects(
        self, vault: str | None = None
    ) -> list[tuple[str, int]]:
        """List all projects with note counts."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        query = """
            SELECT project, COUNT(*) as count
            FROM notes
            WHERE project IS NOT NULL
        """
        params: list[Any] = []

        if vault:
            query += " AND vault_name = ?"
            params.append(vault)

        query += " GROUP BY project ORDER BY count DESC"

        cursor = await self.db.execute(query, params)
        return [(row['project'], row['count']) async for row in cursor]

    async def get_backlinks(self, note_id: int) -> list[SearchResult]:
        """Get all notes that link to this note."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        cursor = await self.db.execute(
            """
            SELECT DISTINCT n.id, n.vault_name, n.relative_path, n.permalink,
                   n.title, n.note_type, n.project,
                   n.created_at, n.updated_at
            FROM notes n
            INNER JOIN wikilinks w ON w.source_note_id = n.id
            WHERE w.target_note_id = ?
            ORDER BY n.updated_at DESC
            """,
            (note_id,),
        )

        results: list[SearchResult] = []
        async for row in cursor:
            # Get tags
            tags_cursor = await self.db.execute(
                "SELECT tag FROM note_tags WHERE note_id = ?", (row['id'],)
            )
            tags = [tag_row['tag'] async for tag_row in tags_cursor]

            # Parse dates
            created_at = None
            if row['created_at']:
                try:
                    created_at = datetime.fromisoformat(row['created_at'])
                except ValueError:
                    pass

            updated_at = None
            if row['updated_at']:
                try:
                    updated_at = datetime.fromisoformat(row['updated_at'])
                except ValueError:
                    pass

            results.append(
                SearchResult(
                    note_id=row['id'],
                    vault_name=row['vault_name'],
                    relative_path=row['relative_path'],
                    permalink=row['permalink'],
                    title=row['title'],
                    note_type=row['note_type'],
                    project=row['project'],
                    snippet="",
                    score=0.0,
                    created_at=created_at,
                    updated_at=updated_at,
                    tags=tags,
                )
            )

        return results

    async def get_recent_notes(
        self,
        limit: int = 20,
        vault: str | None = None,
        project: str | None = None,
    ) -> list[SearchResult]:
        """Get recently updated notes."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        query = """
            SELECT n.id, n.vault_name, n.relative_path, n.permalink,
                   n.title, n.note_type, n.project,
                   n.created_at, n.updated_at
            FROM notes n
            WHERE 1=1
        """
        params: list[Any] = []

        if vault:
            query += " AND n.vault_name = ?"
            params.append(vault)

        if project:
            query += " AND n.project = ?"
            params.append(project)

        query += " ORDER BY n.updated_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self.db.execute(query, params)

        results: list[SearchResult] = []
        async for row in cursor:
            # Get tags
            tags_cursor = await self.db.execute(
                "SELECT tag FROM note_tags WHERE note_id = ?", (row['id'],)
            )
            tags = [tag_row['tag'] async for tag_row in tags_cursor]

            # Parse dates
            created_at = None
            if row['created_at']:
                try:
                    created_at = datetime.fromisoformat(row['created_at'])
                except ValueError:
                    pass

            updated_at = None
            if row['updated_at']:
                try:
                    updated_at = datetime.fromisoformat(row['updated_at'])
                except ValueError:
                    pass

            results.append(
                SearchResult(
                    note_id=row['id'],
                    vault_name=row['vault_name'],
                    relative_path=row['relative_path'],
                    permalink=row['permalink'],
                    title=row['title'],
                    note_type=row['note_type'],
                    project=row['project'],
                    snippet="",
                    score=0.0,
                    created_at=created_at,
                    updated_at=updated_at,
                    tags=tags,
                )
            )

        return results

    # Statistics

    async def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        if not self.db:
            raise RuntimeError("Database not initialized")

        # Total notes
        cursor = await self.db.execute("SELECT COUNT(*) as count FROM notes")
        total_notes = (await cursor.fetchone())['count']

        # Notes by vault
        cursor = await self.db.execute(
            """
            SELECT vault_name, COUNT(*) as count
            FROM notes
            GROUP BY vault_name
            """
        )
        notes_by_vault = {
            row['vault_name']: row['count'] async for row in cursor
        }

        # Notes by type
        cursor = await self.db.execute(
            """
            SELECT note_type, COUNT(*) as count
            FROM notes
            GROUP BY note_type
            """
        )
        notes_by_type = {
            row['note_type']: row['count'] async for row in cursor
        }

        # Total observations
        cursor = await self.db.execute(
            "SELECT COUNT(*) as count FROM observations"
        )
        total_observations = (await cursor.fetchone())['count']

        # Total relations
        cursor = await self.db.execute("SELECT COUNT(*) as count FROM relations")
        total_relations = (await cursor.fetchone())['count']

        # Total tags
        cursor = await self.db.execute(
            "SELECT COUNT(DISTINCT tag) as count FROM note_tags"
        )
        total_tags = (await cursor.fetchone())['count']

        return {
            "total_notes": total_notes,
            "notes_by_vault": notes_by_vault,
            "notes_by_type": notes_by_type,
            "total_observations": total_observations,
            "total_relations": total_relations,
            "total_tags": total_tags,
        }

    async def index_vault(
        self,
        vault_name: str,
        notes: list[IndexedNote],
        full_reindex: bool = False,
    ) -> tuple[int, int, int]:
        """
        Bulk index notes from a vault.

        Returns tuple of (added, updated, removed) counts.
        """
        if not self.db:
            raise RuntimeError("Database not initialized")

        added = 0
        updated = 0
        removed = 0

        # Get existing note paths
        cursor = await self.db.execute(
            "SELECT relative_path FROM notes WHERE vault_name = ?",
            (vault_name,),
        )
        existing_paths = {row['relative_path'] async for row in cursor}
        new_paths = {note.relative_path for note in notes}

        # Remove notes not in new list
        if full_reindex:
            to_remove = existing_paths - new_paths
            for path in to_remove:
                await self.remove_note(vault_name, path)
                removed += len(to_remove)

        # Index all notes
        async with self.db:
            for note in notes:
                # Check if exists
                cursor = await self.db.execute(
                    """
                    SELECT id FROM notes
                    WHERE vault_name = ? AND relative_path = ?
                    """,
                    (note.vault_name, note.relative_path),
                )
                exists = await cursor.fetchone() is not None

                await self.index_note(note)
                if exists:
                    updated += 1
                else:
                    added += 1

        return (added, updated, removed)
