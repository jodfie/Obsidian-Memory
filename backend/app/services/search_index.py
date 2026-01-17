"""Search index service using SQLite FTS5."""

import hashlib
import time
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.models.note import Observation, Relation, Wikilink
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
        self._conn: aiosqlite.Connection | None = None

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            # Enable WAL mode for concurrent reads/writes
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA synchronous=NORMAL")
            await self._conn.commit()
        return self._conn

    async def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""
        conn = await self._get_connection()

        # Create notes table
        await conn.execute("""
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
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_vault ON notes(vault_name)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_project ON notes(project)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_type ON notes(note_type)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_permalink ON notes(permalink)"
        )

        # Create FTS5 virtual table
        await conn.execute("""
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

        # Create tags table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS note_tags (
                note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                tag TEXT NOT NULL,
                PRIMARY KEY (note_id, tag)
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tags_tag ON note_tags(tag)"
        )

        # Create observations table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT,
                line_number INTEGER
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_note ON observations(note_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_category ON observations(category)"
        )

        # Create relations table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                relation_type TEXT NOT NULL,
                target_title TEXT NOT NULL,
                target_note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
                context TEXT
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_note_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_note_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type)"
        )

        # Create wikilinks table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS wikilinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
                target_title TEXT NOT NULL,
                target_note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
                display_text TEXT
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wikilinks_source ON wikilinks(source_note_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wikilinks_target ON wikilinks(target_note_id)"
        )

        # Create FTS triggers
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, title, content, tags, observations)
                VALUES (new.id, new.title, '', '', '');
            END
        """)

        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
                VALUES('delete', old.id, old.title, '', '', '');
            END
        """)

        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
                VALUES('delete', old.id, old.title, '', '', '');
                INSERT INTO notes_fts(rowid, title, content, tags, observations)
                VALUES (new.id, new.title, '', '', '');
            END
        """)

        await conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

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
        self,
        note_id: int,
        query: str,
        max_length: int = 200,
    ) -> str:
        """Generate highlighted snippet for search result."""
        try:
            conn = await self._get_connection()
            fts_query = self._build_fts_query(SearchQuery(query=query))

            result = await conn.execute(
                """
                SELECT snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32)
                FROM notes_fts
                WHERE rowid = ? AND notes_fts MATCH ?
                """,
                (note_id, fts_query),
            )
            row = await result.fetchone()
            return row[0] if row and row[0] else ""
        except Exception:
            # If snippet generation fails, return empty string
            return ""

    async def index_note(self, note: IndexedNote) -> int:
        """
        Index or update a note.

        Returns the note_id.
        """
        conn = await self._get_connection()
        indexed_at = datetime.utcnow().isoformat()

        # Check if note exists
        cursor = await conn.execute(
            """
            SELECT id FROM notes
            WHERE vault_name = ? AND relative_path = ?
            """,
            (note.vault_name, note.relative_path),
        )
        row = await cursor.fetchone()

        if row:
            # Update existing note
            note_id = row[0]

            # Update notes table
            await conn.execute(
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
                    note.created_at.isoformat() if note.created_at else None,
                    note.updated_at.isoformat() if note.updated_at else None,
                    indexed_at,
                    note.file_hash,
                    note_id,
                ),
            )

            # Delete existing related data
            await conn.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
            await conn.execute(
                "DELETE FROM observations WHERE note_id = ?", (note_id,)
            )
            await conn.execute("DELETE FROM relations WHERE source_note_id = ?", (note_id,))
            await conn.execute("DELETE FROM wikilinks WHERE source_note_id = ?", (note_id,))
        else:
            # Insert new note
            cursor = await conn.execute(
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
                    note.created_at.isoformat() if note.created_at else None,
                    note.updated_at.isoformat() if note.updated_at else None,
                    indexed_at,
                    note.file_hash,
                ),
            )
            note_id = cursor.lastrowid
            await conn.commit()

        # Insert tags
        for tag in note.tags:
            await conn.execute(
                "INSERT OR IGNORE INTO note_tags (note_id, tag) VALUES (?, ?)",
                (note_id, tag),
            )

        # Insert observations
        observations_text = []
        for obs in note.observations:
            await conn.execute(
                """
                INSERT INTO observations (note_id, category, content, context, line_number)
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
            observations_text.append(f"{obs.category.value}: {obs.content}")

        # Insert relations (resolve targets later)
        for rel in note.relations:
            target_note_id = await self.resolve_wikilink(
                rel.target, from_vault=note.vault_name
            )
            await conn.execute(
                """
                INSERT INTO relations (
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

        # Insert wikilinks
        for wl in note.wikilinks:
            target_note_id = await self.resolve_wikilink(
                wl.target, from_vault=note.vault_name
            )
            await conn.execute(
                """
                INSERT INTO wikilinks (source_note_id, target_title, target_note_id, display_text)
                VALUES (?, ?, ?, ?)
                """,
                (note_id, wl.target, target_note_id, wl.display_text),
            )

        # Update FTS index (delete old, insert new)
        tags_str = ' '.join(note.tags)
        obs_str = ' '.join(observations_text)

        # Delete old FTS entry
        await conn.execute(
            """
            INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
            VALUES('delete', ?, '', '', '', '')
            """,
            (note_id,),
        )

        # Insert new FTS entry
        await conn.execute(
            """
            INSERT INTO notes_fts(rowid, title, content, tags, observations)
            VALUES (?, ?, ?, ?, ?)
            """,
            (note_id, note.title, note.content, tags_str, obs_str),
        )

        await conn.commit()
        return note_id

    async def remove_note(
        self,
        vault_name: str,
        relative_path: str,
    ) -> bool:
        """Remove a note from the index. Returns True if note was found."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "DELETE FROM notes WHERE vault_name = ? AND relative_path = ?",
            (vault_name, relative_path),
        )
        await conn.commit()
        return cursor.rowcount > 0

    async def needs_reindex(
        self,
        vault_name: str,
        relative_path: str,
        file_hash: str,
    ) -> bool:
        """Check if a note needs reindexing based on file hash."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            """
            SELECT file_hash FROM notes
            WHERE vault_name = ? AND relative_path = ?
            """,
            (vault_name, relative_path),
        )
        row = await cursor.fetchone()
        if not row:
            return True
        return row[0] != file_hash

    async def resolve_wikilink(
        self,
        target_title: str,
        from_vault: str | None = None,
    ) -> int | None:
        """
        Resolve a wikilink target to a note_id.

        Search order:
        1. Exact title match in same vault
        2. Exact permalink match
        3. Exact title match in any vault
        4. Case-insensitive title match
        """
        conn = await self._get_connection()

        # 1. Exact title match in same vault
        if from_vault:
            cursor = await conn.execute(
                "SELECT id FROM notes WHERE vault_name = ? AND title = ? LIMIT 1",
                (from_vault, target_title),
            )
            row = await cursor.fetchone()
            if row:
                return row[0]

        # 2. Exact permalink match
        cursor = await conn.execute(
            "SELECT id FROM notes WHERE permalink = ? LIMIT 1",
            (target_title,),
        )
        row = await cursor.fetchone()
        if row:
            return row[0]

        # 3. Exact title match in any vault
        cursor = await conn.execute(
            "SELECT id FROM notes WHERE title = ? LIMIT 1",
            (target_title,),
        )
        row = await cursor.fetchone()
        if row:
            return row[0]

        # 4. Case-insensitive title match
        cursor = await conn.execute(
            "SELECT id FROM notes WHERE LOWER(title) = LOWER(?) LIMIT 1",
            (target_title,),
        )
        row = await cursor.fetchone()
        if row:
            return row[0]

        return None

    async def search(self, query: SearchQuery) -> SearchResults:
        """
        Execute a search query.

        Returns results with highlighted snippets.
        """
        start_time = time.time()
        conn = await self._get_connection()
        fts_query = self._build_fts_query(query)

        # Build WHERE clause for filters
        where_clauses = []
        params: list[object] = []

        if query.vault:
            where_clauses.append("n.vault_name = ?")
            params.append(query.vault)

        if query.project:
            where_clauses.append("n.project = ?")
            params.append(query.project)

        if query.note_type:
            where_clauses.append("n.note_type = ?")
            params.append(query.note_type)

        if query.tags:
            # AND tags - note must have all tags
            for tag in query.tags:
                where_clauses.append(
                    "EXISTS (SELECT 1 FROM note_tags WHERE note_id = n.id AND tag = ?)"
                )
                params.append(tag)

        if query.tags_any:
            # OR tags - note must have at least one tag
            tag_placeholders = ','.join(['?'] * len(query.tags_any))
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM note_tags WHERE note_id = n.id AND tag IN ({tag_placeholders}))"
            )
            params.extend(query.tags_any)

        if query.observation_category:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM observations WHERE note_id = n.id AND category = ?)"
            )
            params.append(query.observation_category)

        if query.created_after:
            where_clauses.append("n.created_at >= ?")
            params.append(query.created_after.isoformat())

        if query.created_before:
            where_clauses.append("n.created_at <= ?")
            params.append(query.created_before.isoformat())

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Build ORDER BY clause
        order_by = {
            SortOrder.RELEVANCE: "rank",
            SortOrder.CREATED_DESC: "n.created_at DESC",
            SortOrder.CREATED_ASC: "n.created_at ASC",
            SortOrder.UPDATED_DESC: "n.updated_at DESC",
            SortOrder.UPDATED_ASC: "n.updated_at ASC",
            SortOrder.TITLE_ASC: "n.title ASC",
        }[query.sort]

        # Build query
        if query.sort == SortOrder.RELEVANCE:
            sql = f"""
                SELECT
                    n.id, n.vault_name, n.relative_path, n.permalink, n.title,
                    n.note_type, n.project, n.created_at, n.updated_at,
                    bm25(notes_fts) as rank
                FROM notes_fts
                JOIN notes n ON notes_fts.rowid = n.id
                WHERE notes_fts MATCH ? AND {where_sql}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
            """
            params = [fts_query] + params + [query.limit, query.offset]
        else:
            sql = f"""
                SELECT
                    n.id, n.vault_name, n.relative_path, n.permalink, n.title,
                    n.note_type, n.project, n.created_at, n.updated_at,
                    0.0 as rank
                FROM notes n
                WHERE EXISTS (
                    SELECT 1 FROM notes_fts
                    WHERE notes_fts.rowid = n.id AND notes_fts MATCH ?
                ) AND {where_sql}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
            """
            params = [fts_query] + params + [query.limit, query.offset]

        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()

        # Get total count
        count_sql = f"""
            SELECT COUNT(DISTINCT n.id)
            FROM notes n
            WHERE EXISTS (
                SELECT 1 FROM notes_fts
                WHERE notes_fts.rowid = n.id AND notes_fts MATCH ?
            ) AND {where_sql}
        """
        count_params = [fts_query] + params[1:-2]  # Remove limit/offset
        count_cursor = await conn.execute(count_sql, count_params)
        total_count = (await count_cursor.fetchone())[0]

        # Build results
        results: list[SearchResult] = []
        for row in rows:
            note_id = row[0]
            snippet = await self._generate_snippet(note_id, query.query)

            # Get tags
            tag_cursor = await conn.execute(
                "SELECT tag FROM note_tags WHERE note_id = ?", (note_id,)
            )
            tags = [tag_row[0] for tag_row in await tag_cursor.fetchall()]

            # Parse datetimes
            created_at = None
            if row[7]:
                try:
                    created_at = datetime.fromisoformat(row[7])
                except ValueError:
                    pass

            updated_at = None
            if row[8]:
                try:
                    updated_at = datetime.fromisoformat(row[8])
                except ValueError:
                    pass

            results.append(
                SearchResult(
                    note_id=note_id,
                    vault_name=row[1],
                    relative_path=row[2],
                    permalink=row[3],
                    title=row[4],
                    note_type=row[5],
                    project=row[6],
                    snippet=snippet,
                    score=row[9] if len(row) > 9 else 0.0,
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
        self,
        note_id: int,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Find notes similar to a given note."""
        conn = await self._get_connection()

        # Get note content
        cursor = await conn.execute(
            "SELECT title, content FROM notes_fts WHERE rowid = ?", (note_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return []

        # Search for similar notes using content
        search_query = SearchQuery(query=row[1] or row[0], limit=limit + 1)
        results = await self.search(search_query)

        # Filter out the original note
        return [r for r in results.results if r.note_id != note_id][:limit]

    async def get_note_by_id(self, note_id: int) -> IndexedNote | None:
        """Get full indexed note by ID."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            """
            SELECT vault_name, relative_path, permalink, title, note_type,
                   project, created_at, updated_at, file_hash
            FROM notes WHERE id = ?
            """,
            (note_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Get content from FTS (FTS5 stores content in the content table)
        # For now, we'll store content in a separate field or reconstruct from raw_content
        # Since FTS5 doesn't easily allow retrieving original content, we'll use empty string
        # In a real implementation, you might want to store content separately
        content = ""

        # Get tags
        tag_cursor = await conn.execute(
            "SELECT tag FROM note_tags WHERE note_id = ?", (note_id,)
        )
        tags = [tag_row[0] for tag_row in await tag_cursor.fetchall()]

        # Get observations
        obs_cursor = await conn.execute(
            """
            SELECT category, content, context, line_number
            FROM observations WHERE note_id = ?
            """,
            (note_id,),
        )
        observations = []
        for obs_row in await obs_cursor.fetchall():
            from app.models.note import ObservationCategory

            try:
                category = ObservationCategory(obs_row[0])
                observations.append(
                    Observation(
                        category=category,
                        content=obs_row[1],
                        context=obs_row[2],
                        line_number=obs_row[3] or 0,
                        tags=[],
                    )
                )
            except ValueError:
                pass

        # Get relations
        rel_cursor = await conn.execute(
            """
            SELECT relation_type, target_title, context
            FROM relations WHERE source_note_id = ?
            """,
            (note_id,),
        )
        relations = []
        for rel_row in await rel_cursor.fetchall():
            from app.models.note import RelationType

            try:
                rel_type = RelationType(rel_row[0])
                relations.append(
                    Relation(
                        relation_type=rel_type,
                        target=rel_row[1],
                        context=rel_row[2],
                        line_number=0,
                    )
                )
            except ValueError:
                pass

        # Get wikilinks
        wl_cursor = await conn.execute(
            """
            SELECT target_title, display_text
            FROM wikilinks WHERE source_note_id = ?
            """,
            (note_id,),
        )
        wikilinks = []
        for wl_row in await wl_cursor.fetchall():
            wikilinks.append(
                Wikilink(
                    target=wl_row[0],
                    display_text=wl_row[1],
                    line_number=0,
                    column=0,
                )
            )

        # Parse datetimes
        created_at = None
        if row[6]:
            try:
                created_at = datetime.fromisoformat(row[6])
            except ValueError:
                pass

        updated_at = None
        if row[7]:
            try:
                updated_at = datetime.fromisoformat(row[7])
            except ValueError:
                pass

        return IndexedNote(
            vault_name=row[0],
            relative_path=row[1],
            permalink=row[2],
            title=row[3],
            note_type=row[4],
            project=row[5],
            content=content,
            tags=tags,
            observations=observations,
            relations=relations,
            wikilinks=wikilinks,
            created_at=created_at,
            updated_at=updated_at,
            file_hash=row[8],
        )

    async def get_note_by_permalink(self, permalink: str) -> IndexedNote | None:
        """Get note by permalink."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT id FROM notes WHERE permalink = ?", (permalink,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return await self.get_note_by_id(row[0])

    async def get_note_by_path(
        self,
        vault_name: str,
        relative_path: str,
    ) -> IndexedNote | None:
        """Get note by vault and path."""
        conn = await self._get_connection()
        cursor = await conn.execute(
            "SELECT id FROM notes WHERE vault_name = ? AND relative_path = ?",
            (vault_name, relative_path),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return await self.get_note_by_id(row[0])

    async def list_tags(
        self,
        vault: str | None = None,
        project: str | None = None,
    ) -> list[tuple[str, int]]:
        """List all tags with counts."""
        conn = await self._get_connection()
        if vault and project:
            cursor = await conn.execute(
                """
                SELECT tag, COUNT(*) as count
                FROM note_tags
                JOIN notes ON note_tags.note_id = notes.id
                WHERE notes.vault_name = ? AND notes.project = ?
                GROUP BY tag
                ORDER BY count DESC, tag ASC
                """,
                (vault, project),
            )
        elif vault:
            cursor = await conn.execute(
                """
                SELECT tag, COUNT(*) as count
                FROM note_tags
                JOIN notes ON note_tags.note_id = notes.id
                WHERE notes.vault_name = ?
                GROUP BY tag
                ORDER BY count DESC, tag ASC
                """,
                (vault,),
            )
        elif project:
            cursor = await conn.execute(
                """
                SELECT tag, COUNT(*) as count
                FROM note_tags
                JOIN notes ON note_tags.note_id = notes.id
                WHERE notes.project = ?
                GROUP BY tag
                ORDER BY count DESC, tag ASC
                """,
                (project,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT tag, COUNT(*) as count
                FROM note_tags
                GROUP BY tag
                ORDER BY count DESC, tag ASC
                """
            )
        return [(row[0], row[1]) for row in await cursor.fetchall()]

    async def list_projects(
        self,
        vault: str | None = None,
    ) -> list[tuple[str, int]]:
        """List all projects with note counts."""
        conn = await self._get_connection()
        if vault:
            cursor = await conn.execute(
                """
                SELECT project, COUNT(*) as count
                FROM notes
                WHERE vault_name = ? AND project IS NOT NULL
                GROUP BY project
                ORDER BY count DESC, project ASC
                """,
                (vault,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT project, COUNT(*) as count
                FROM notes
                WHERE project IS NOT NULL
                GROUP BY project
                ORDER BY count DESC, project ASC
                """
            )
        return [(row[0], row[1]) for row in await cursor.fetchall()]

    async def get_backlinks(self, note_id: int) -> list[SearchResult]:
        """Get all notes that link to this note."""
        conn = await self._get_connection()

        # Get notes that link via wikilinks
        cursor = await conn.execute(
            """
            SELECT DISTINCT n.id, n.vault_name, n.relative_path, n.permalink,
                   n.title, n.note_type, n.project, n.created_at, n.updated_at
            FROM notes n
            JOIN wikilinks w ON n.id = w.source_note_id
            WHERE w.target_note_id = ?
            """,
            (note_id,),
        )
        rows = await cursor.fetchall()

        results: list[SearchResult] = []
        for row in rows:
            # Get tags
            tag_cursor = await conn.execute(
                "SELECT tag FROM note_tags WHERE note_id = ?", (row[0],)
            )
            tags = [tag_row[0] for tag_row in await tag_cursor.fetchall()]

            created_at = None
            if row[7]:
                try:
                    created_at = datetime.fromisoformat(row[7])
                except ValueError:
                    pass

            updated_at = None
            if row[8]:
                try:
                    updated_at = datetime.fromisoformat(row[8])
                except ValueError:
                    pass

            results.append(
                SearchResult(
                    note_id=row[0],
                    vault_name=row[1],
                    relative_path=row[2],
                    permalink=row[3],
                    title=row[4],
                    note_type=row[5],
                    project=row[6],
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
        conn = await self._get_connection()

        where_clauses = []
        params: list[object] = []

        if vault:
            where_clauses.append("vault_name = ?")
            params.append(vault)

        if project:
            where_clauses.append("project = ?")
            params.append(project)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        cursor = await conn.execute(
            f"""
            SELECT id, vault_name, relative_path, permalink, title, note_type,
                   project, created_at, updated_at
            FROM notes
            WHERE {where_sql}
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            params + [limit],
        )
        rows = await cursor.fetchall()

        results: list[SearchResult] = []
        for row in rows:
            # Get tags
            tag_cursor = await conn.execute(
                "SELECT tag FROM note_tags WHERE note_id = ?", (row[0],)
            )
            tags = [tag_row[0] for tag_row in await tag_cursor.fetchall()]

            created_at = None
            if row[7]:
                try:
                    created_at = datetime.fromisoformat(row[7])
                except ValueError:
                    pass

            updated_at = None
            if row[8]:
                try:
                    updated_at = datetime.fromisoformat(row[8])
                except ValueError:
                    pass

            results.append(
                SearchResult(
                    note_id=row[0],
                    vault_name=row[1],
                    relative_path=row[2],
                    permalink=row[3],
                    title=row[4],
                    note_type=row[5],
                    project=row[6],
                    snippet="",
                    score=0.0,
                    created_at=created_at,
                    updated_at=updated_at,
                    tags=tags,
                )
            )

        return results

    async def get_stats(self) -> dict:
        """Get index statistics."""
        conn = await self._get_connection()

        # Total notes
        cursor = await conn.execute("SELECT COUNT(*) FROM notes")
        total_notes = (await cursor.fetchone())[0]

        # Notes by vault
        cursor = await conn.execute(
            "SELECT vault_name, COUNT(*) FROM notes GROUP BY vault_name"
        )
        notes_by_vault = {row[0]: row[1] for row in await cursor.fetchall()}

        # Notes by type
        cursor = await conn.execute(
            "SELECT note_type, COUNT(*) FROM notes GROUP BY note_type"
        )
        notes_by_type = {row[0]: row[1] for row in await cursor.fetchall()}

        # Total observations
        cursor = await conn.execute("SELECT COUNT(*) FROM observations")
        total_observations = (await cursor.fetchone())[0]

        # Total relations
        cursor = await conn.execute("SELECT COUNT(*) FROM relations")
        total_relations = (await cursor.fetchone())[0]

        # Total tags
        cursor = await conn.execute("SELECT COUNT(DISTINCT tag) FROM note_tags")
        total_tags = (await cursor.fetchone())[0]

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
        conn = await self._get_connection()

        added = 0
        updated = 0
        removed = 0

        # Get existing notes in vault
        cursor = await conn.execute(
            "SELECT id, relative_path, file_hash FROM notes WHERE vault_name = ?",
            (vault_name,),
        )
        existing = {row[1]: (row[0], row[2]) for row in await cursor.fetchall()}

        # Index each note
        indexed_paths = set()
        for note in notes:
            indexed_paths.add(note.relative_path)
            if note.relative_path in existing:
                old_id, old_hash = existing[note.relative_path]
                if old_hash != note.file_hash:
                    await self.index_note(note)
                    updated += 1
            else:
                await self.index_note(note)
                added += 1

        # Remove notes not in the list if full_reindex
        if full_reindex:
            for path in existing:
                if path not in indexed_paths:
                    await self.remove_note(vault_name, path)
                    removed += 1

        return (added, updated, removed)
