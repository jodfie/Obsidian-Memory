# Search Index Specification

## Overview

The Search Index provides full-text search across all notes using SQLite with FTS5 extension, enabling fast queries with relevance ranking and filtering.

## Scope

This spec covers ONLY indexing and search. It does NOT cover:
- File I/O (see `core-vault-manager.md`)
- Parsing markdown (see `core-markdown-parser.md`)
- Graph queries (see `graph-engine.md`)

## Database Schema

### Core Tables

```sql
-- Notes metadata table
CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vault_name TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    permalink TEXT UNIQUE,
    title TEXT NOT NULL,
    note_type TEXT DEFAULT 'note',
    project TEXT,
    created_at TEXT,  -- ISO 8601
    updated_at TEXT,  -- ISO 8601
    indexed_at TEXT NOT NULL,  -- When we indexed it
    file_hash TEXT NOT NULL,  -- For change detection

    UNIQUE(vault_name, relative_path)
);

CREATE INDEX idx_notes_vault ON notes(vault_name);
CREATE INDEX idx_notes_project ON notes(project);
CREATE INDEX idx_notes_type ON notes(note_type);
CREATE INDEX idx_notes_permalink ON notes(permalink);

-- Full-text search index
CREATE VIRTUAL TABLE notes_fts USING fts5(
    title,
    content,
    tags,
    observations,
    content='notes',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Tags table (for filtering)
CREATE TABLE note_tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (note_id, tag)
);

CREATE INDEX idx_tags_tag ON note_tags(tag);

-- Observations table
CREATE TABLE observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    context TEXT,
    line_number INTEGER
);

CREATE INDEX idx_observations_note ON observations(note_id);
CREATE INDEX idx_observations_category ON observations(category);

-- Relations table
CREATE TABLE relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    target_title TEXT NOT NULL,
    target_note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    context TEXT
);

CREATE INDEX idx_relations_source ON relations(source_note_id);
CREATE INDEX idx_relations_target ON relations(target_note_id);
CREATE INDEX idx_relations_type ON relations(relation_type);

-- Wikilinks table (for backlink queries)
CREATE TABLE wikilinks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL,
    target_note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    display_text TEXT
);

CREATE INDEX idx_wikilinks_source ON wikilinks(source_note_id);
CREATE INDEX idx_wikilinks_target ON wikilinks(target_note_id);

-- FTS triggers for keeping index in sync
CREATE TRIGGER notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content, tags, observations)
    VALUES (new.id, new.title, '', '', '');
END;

CREATE TRIGGER notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
    VALUES('delete', old.id, old.title, '', '', '');
END;

CREATE TRIGGER notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content, tags, observations)
    VALUES('delete', old.id, old.title, '', '', '');
    INSERT INTO notes_fts(rowid, title, content, tags, observations)
    VALUES (new.id, new.title, '', '', '');
END;
```

## Data Structures

### SearchQuery

```python
from pydantic import BaseModel
from enum import Enum

class SortOrder(str, Enum):
    RELEVANCE = "relevance"
    CREATED_DESC = "created_desc"
    CREATED_ASC = "created_asc"
    UPDATED_DESC = "updated_desc"
    UPDATED_ASC = "updated_asc"
    TITLE_ASC = "title_asc"

class SearchQuery(BaseModel):
    """Search query parameters."""
    query: str  # FTS5 query string
    vault: str | None = None  # Filter by vault
    project: str | None = None  # Filter by project
    note_type: str | None = None  # Filter by type
    tags: list[str] = []  # Filter by tags (AND)
    tags_any: list[str] = []  # Filter by tags (OR)
    observation_category: str | None = None  # Filter by observation type
    created_after: datetime | None = None
    created_before: datetime | None = None
    sort: SortOrder = SortOrder.RELEVANCE
    limit: int = 50
    offset: int = 0
```

### SearchResult

```python
class SearchResult(BaseModel):
    """Single search result."""
    note_id: int
    vault_name: str
    relative_path: str
    permalink: str | None
    title: str
    note_type: str
    project: str | None
    snippet: str  # Highlighted excerpt
    score: float  # Relevance score
    created_at: datetime | None
    updated_at: datetime | None
    tags: list[str]

class SearchResults(BaseModel):
    """Search results with pagination."""
    results: list[SearchResult]
    total_count: int
    query: str
    took_ms: float
```

### IndexedNote

```python
class IndexedNote(BaseModel):
    """Note data for indexing."""
    vault_name: str
    relative_path: str
    permalink: str | None
    title: str
    note_type: str
    project: str | None
    content: str  # Full content for FTS
    tags: list[str]
    observations: list[Observation]
    relations: list[Relation]
    wikilinks: list[Wikilink]
    created_at: datetime | None
    updated_at: datetime | None
    file_hash: str
```

## Interface

### SearchIndex Class

```python
class SearchIndex:
    """Full-text search index using SQLite FTS5."""

    def __init__(self, db_path: Path) -> None:
        """Initialize with database path."""

    async def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""

    # Indexing Operations
    async def index_note(self, note: IndexedNote) -> int:
        """
        Index or update a note.

        Returns the note_id.

        If note already exists (by vault+path), updates it.
        Resolves wikilink and relation targets to note_ids.
        """

    async def remove_note(
        self,
        vault_name: str,
        relative_path: str
    ) -> bool:
        """
        Remove a note from the index.

        Returns True if note was found and removed.
        """

    async def index_vault(
        self,
        vault_name: str,
        notes: list[IndexedNote],
        full_reindex: bool = False
    ) -> tuple[int, int, int]:
        """
        Bulk index notes from a vault.

        Args:
            vault_name: Vault being indexed
            notes: All notes to index
            full_reindex: If True, removes notes not in list

        Returns:
            Tuple of (added, updated, removed) counts
        """

    async def needs_reindex(
        self,
        vault_name: str,
        relative_path: str,
        file_hash: str
    ) -> bool:
        """Check if a note needs reindexing based on file hash."""

    # Search Operations
    async def search(self, query: SearchQuery) -> SearchResults:
        """
        Execute a search query.

        FTS5 query syntax supported:
        - Simple terms: "authentication"
        - Phrases: '"JWT tokens"'
        - AND: "auth AND jwt"
        - OR: "auth OR session"
        - NOT: "auth NOT cookie"
        - Prefix: "auth*"
        - Column: "title:authentication"

        Returns results with highlighted snippets.
        """

    async def search_similar(
        self,
        note_id: int,
        limit: int = 10
    ) -> list[SearchResult]:
        """
        Find notes similar to a given note.

        Uses FTS5 BM25 ranking on note content.
        """

    # Query Helpers
    async def get_note_by_id(self, note_id: int) -> IndexedNote | None:
        """Get full indexed note by ID."""

    async def get_note_by_permalink(self, permalink: str) -> IndexedNote | None:
        """Get note by permalink."""

    async def get_note_by_path(
        self,
        vault_name: str,
        relative_path: str
    ) -> IndexedNote | None:
        """Get note by vault and path."""

    async def resolve_wikilink(
        self,
        target_title: str,
        from_vault: str | None = None
    ) -> int | None:
        """
        Resolve a wikilink target to a note_id.

        Search order:
        1. Exact title match in same vault
        2. Exact permalink match
        3. Exact title match in any vault
        4. Case-insensitive title match
        """

    # Aggregation Queries
    async def list_tags(
        self,
        vault: str | None = None,
        project: str | None = None
    ) -> list[tuple[str, int]]:
        """List all tags with counts."""

    async def list_projects(
        self,
        vault: str | None = None
    ) -> list[tuple[str, int]]:
        """List all projects with note counts."""

    async def get_backlinks(
        self,
        note_id: int
    ) -> list[SearchResult]:
        """Get all notes that link to this note."""

    async def get_recent_notes(
        self,
        limit: int = 20,
        vault: str | None = None,
        project: str | None = None
    ) -> list[SearchResult]:
        """Get recently updated notes."""

    # Statistics
    async def get_stats(self) -> dict:
        """
        Get index statistics.

        Returns:
            {
                "total_notes": int,
                "notes_by_vault": dict[str, int],
                "notes_by_type": dict[str, int],
                "total_observations": int,
                "total_relations": int,
                "total_tags": int
            }
        """
```

## FTS5 Query Building

```python
def _build_fts_query(self, query: SearchQuery) -> str:
    """Build FTS5 MATCH clause from search query."""

    # Escape special FTS5 characters
    def escape_fts(term: str) -> str:
        # Quote terms with special chars
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
```

## Snippet Generation

```python
async def _generate_snippet(
    self,
    note_id: int,
    query: str,
    max_length: int = 200
) -> str:
    """Generate highlighted snippet for search result."""

    # Use FTS5 snippet function
    result = await self.db.execute("""
        SELECT snippet(notes_fts, 1, '<mark>', '</mark>', '...', 32)
        FROM notes_fts
        WHERE rowid = ? AND notes_fts MATCH ?
    """, (note_id, query))

    row = await result.fetchone()
    return row[0] if row else ""
```

## Change Detection

Use content hash for efficient change detection:

```python
import hashlib

def compute_file_hash(content: str) -> str:
    """Compute hash for change detection."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
```

## Database Location

Default: `~/.obsidian-memory/index.db`

Can be overridden in config.

## Concurrency

- Use aiosqlite for async operations
- Enable WAL mode for concurrent reads/writes:
  ```sql
  PRAGMA journal_mode=WAL;
  PRAGMA synchronous=NORMAL;
  ```
- Use connection pooling for multiple concurrent queries

## File Location

```
backend/
└── app/
    └── services/
        └── search_index.py
```

## Tests Required

```
backend/tests/
└── services/
    └── test_search_index.py
        ├── test_initialize_creates_tables
        ├── test_index_note_new
        ├── test_index_note_update
        ├── test_remove_note
        ├── test_search_simple_term
        ├── test_search_phrase
        ├── test_search_boolean_and
        ├── test_search_boolean_or
        ├── test_search_boolean_not
        ├── test_search_prefix
        ├── test_search_column_specific
        ├── test_search_filter_vault
        ├── test_search_filter_project
        ├── test_search_filter_tags
        ├── test_search_filter_type
        ├── test_search_filter_date_range
        ├── test_search_sort_relevance
        ├── test_search_sort_date
        ├── test_search_pagination
        ├── test_search_similar
        ├── test_resolve_wikilink_exact
        ├── test_resolve_wikilink_permalink
        ├── test_resolve_wikilink_case_insensitive
        ├── test_get_backlinks
        ├── test_list_tags
        ├── test_list_projects
        ├── test_get_stats
        ├── test_needs_reindex
        └── test_bulk_index_vault
```

## Dependencies

- `aiosqlite` - Async SQLite
- `pydantic` - Data validation

## Performance Considerations

- FTS5 with porter stemmer handles ~10k notes efficiently
- Batch indexing for vault syncs (use transactions)
- Snippet generation is expensive - cache or limit
- Consider periodic VACUUM for large indexes
- BM25 ranking is built into FTS5
