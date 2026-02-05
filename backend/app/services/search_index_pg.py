"""Postgres full-text search service using to_tsvector and to_tsquery.

This module provides PostgresSearchIndex class for full-text search against
notes stored in Postgres (Supabase). It replaces SQLite FTS5 when in Postgres mode.

Features:
- Full-text search with `to_tsvector` and `to_tsquery`
- Relevance ranking with `ts_rank`
- Snippet highlighting with `ts_headline`
- Support for quoted phrases using `<->` (FOLLOWED BY) operator
- User isolation via user_id filtering

Usage:
    from app.db import get_db
    from app.services.search_index_pg import PostgresSearchIndex

    async def search_notes(
        query: str,
        user_id: UUID,
        db: AsyncSession = Depends(get_db),
    ):
        search_index = PostgresSearchIndex(db)
        results = await search_index.search(query, user_id)
        return results
"""

import logging
import re
import time
from uuid import UUID

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import NoteModel
from app.schemas.search import SearchQuery, SearchResult, SearchResults

logger = logging.getLogger(__name__)


class PostgresSearchIndex:
    """Postgres full-text search implementation using tsvector/tsquery.

    This class provides async methods for searching notes stored in Postgres
    using native full-text search capabilities.

    Attributes:
        session: SQLAlchemy async session for database operations.
    """

    # Default text search configuration (language)
    TS_CONFIG = "english"

    # Headline configuration for snippet generation
    HEADLINE_OPTIONS = "StartSel=<b>, StopSel=</b>, MaxWords=35, MinWords=15, MaxFragments=3"

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            session: SQLAlchemy AsyncSession instance.
        """
        self._session = session

    def _parse_query(self, query: str) -> str:
        """Parse a user query into a Postgres tsquery string.

        Handles:
        - Plain words: converted to AND-ed terms
        - Quoted phrases: converted to <-> (FOLLOWED BY) sequences
        - Prefix matching: word* becomes word:*

        Args:
            query: User's search query string.

        Returns:
            A tsquery-compatible string for plainto_tsquery or to_tsquery.

        Examples:
            >>> _parse_query("hello world")
            "hello & world"
            >>> _parse_query('"exact phrase"')
            "exact <-> phrase"
            >>> _parse_query('python "async await" tutorial')
            "python & async <-> await & tutorial"
            >>> _parse_query("test*")
            "test:*"
        """
        if not query or not query.strip():
            return ""

        query = query.strip()
        parts: list[str] = []

        # Extract quoted phrases first
        # Matches both "double quotes" and 'single quotes'
        phrase_pattern = r'"([^"]+)"|\'([^\']+)\''

        # Track position for extracting non-quoted parts
        last_end = 0
        quoted_ranges: list[tuple[int, int]] = []

        for match in re.finditer(phrase_pattern, query):
            # Get the phrase content (from either capture group)
            phrase = match.group(1) or match.group(2)
            start, end = match.span()
            quoted_ranges.append((start, end))

            # Process any text before this quote
            if start > last_end:
                before_text = query[last_end:start].strip()
                if before_text:
                    # Split into words and add as AND terms
                    words = self._tokenize_words(before_text)
                    parts.extend(words)

            # Convert phrase to FOLLOWED BY sequence
            phrase_words = phrase.split()
            if len(phrase_words) > 1:
                # Multiple words: join with <-> for adjacency
                phrase_query = " <-> ".join(
                    self._sanitize_term(w) for w in phrase_words if w
                )
                if phrase_query:
                    parts.append(f"({phrase_query})")
            elif phrase_words:
                # Single word in quotes: treat as normal term
                parts.append(self._sanitize_term(phrase_words[0]))

            last_end = end

        # Process any remaining text after the last quote
        if last_end < len(query):
            remaining = query[last_end:].strip()
            if remaining:
                words = self._tokenize_words(remaining)
                parts.extend(words)

        # If no quoted phrases were found, process entire query
        if not quoted_ranges:
            parts = self._tokenize_words(query)

        # Join all parts with AND operator
        if not parts:
            return ""

        return " & ".join(parts)

    def _tokenize_words(self, text: str) -> list[str]:
        """Tokenize text into search terms.

        Handles prefix matching (word*) and removes invalid characters.

        Args:
            text: Text to tokenize.

        Returns:
            List of sanitized search terms.
        """
        words = text.split()
        result = []

        for word in words:
            word = word.strip()
            if not word:
                continue

            # Check for prefix matching
            if word.endswith("*"):
                base = self._sanitize_term(word[:-1])
                if base:
                    result.append(f"{base}:*")
            else:
                term = self._sanitize_term(word)
                if term:
                    result.append(term)

        return result

    def _sanitize_term(self, term: str) -> str:
        """Sanitize a single search term for tsquery.

        Removes characters that are invalid in tsquery and could cause syntax errors.

        Args:
            term: Single search term.

        Returns:
            Sanitized term safe for use in tsquery.
        """
        # Remove tsquery special characters: & | ! ( ) < > : * '
        # Keep alphanumeric, hyphens, and underscores
        sanitized = re.sub(r"[&|!()<>:*'\"\s]", "", term)

        # Remove leading/trailing hyphens
        sanitized = sanitized.strip("-_")

        return sanitized

    async def search(
        self,
        query: str,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResults:
        """Execute a full-text search against notes.

        Uses Postgres to_tsvector and to_tsquery for matching, ts_rank for
        relevance scoring, and ts_headline for snippet generation.

        Args:
            query: Search query string. Supports:
                - Plain words (ANDed together)
                - Quoted phrases for exact matching
                - Prefix matching with * suffix
            user_id: UUID of the requesting user (for security filtering).
            limit: Maximum number of results (default 20, max 100).
            offset: Number of results to skip for pagination.

        Returns:
            SearchResults containing matching notes with snippets and ranking.

        Examples:
            # Basic search
            results = await search_index.search("python async", user_id)

            # Phrase search
            results = await search_index.search('"error handling"', user_id)

            # Prefix search
            results = await search_index.search("implement*", user_id)
        """
        start_time = time.time()

        # Clamp pagination parameters
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        # Parse the query into tsquery format
        parsed_query = self._parse_query(query)

        if not parsed_query:
            # Empty query - return empty results
            return SearchResults(
                results=[],
                total_count=0,
                query=query,
                took_ms=0.0,
                limit=limit,
                offset=offset,
            )

        logger.debug(f"Parsed query: '{query}' -> '{parsed_query}'")

        try:
            # Build the search query using SQLAlchemy func for Postgres functions
            # Create the tsvector from title and content
            ts_vector = func.to_tsvector(
                literal_column(f"'{self.TS_CONFIG}'"),
                func.coalesce(NoteModel.title, literal_column("''"))
                + literal_column("' '")
                + func.coalesce(NoteModel.content, literal_column("''")),
            )

            # Create the tsquery from parsed user input
            ts_query = func.to_tsquery(
                literal_column(f"'{self.TS_CONFIG}'"),
                literal_column(f"'{parsed_query}'"),
            )

            # Calculate rank using ts_rank
            rank = func.ts_rank(ts_vector, ts_query)

            # Generate headline (snippet with highlighting)
            # Combine title and content for headline generation
            headline_text = func.coalesce(NoteModel.title, literal_column("''")) + literal_column(
                "' ... '"
            ) + func.coalesce(NoteModel.content, literal_column("''"))

            headline = func.ts_headline(
                literal_column(f"'{self.TS_CONFIG}'"),
                headline_text,
                ts_query,
                literal_column(f"'{self.HEADLINE_OPTIONS}'"),
            )

            # Count total matching results
            count_stmt = (
                select(func.count(NoteModel.id))
                .where(
                    NoteModel.user_id == str(user_id),
                    ts_vector.op("@@")(ts_query),
                )
            )
            count_result = await self._session.execute(count_stmt)
            total_count = count_result.scalar_one()

            # Fetch matching results with ranking
            search_stmt = (
                select(
                    NoteModel.id,
                    NoteModel.path,
                    NoteModel.title,
                    NoteModel.updated_at,
                    NoteModel.created_at,
                    headline.label("snippet"),
                    rank.label("rank"),
                )
                .where(
                    NoteModel.user_id == str(user_id),
                    ts_vector.op("@@")(ts_query),
                )
                .order_by(rank.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await self._session.execute(search_stmt)
            rows = result.all()

            # Convert to SearchResult objects
            search_results = [
                SearchResult(
                    note_id=UUID(row.id),
                    path=row.path,
                    title=row.title,
                    snippet=row.snippet or "",
                    rank=float(row.rank) if row.rank else 0.0,
                    updated_at=row.updated_at,
                    created_at=row.created_at,
                )
                for row in rows
            ]

            took_ms = (time.time() - start_time) * 1000

            return SearchResults(
                results=search_results,
                total_count=total_count,
                query=query,
                took_ms=took_ms,
                limit=limit,
                offset=offset,
            )

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            # Return empty results on error rather than raising
            # This provides graceful degradation for malformed queries
            took_ms = (time.time() - start_time) * 1000
            return SearchResults(
                results=[],
                total_count=0,
                query=query,
                took_ms=took_ms,
                limit=limit,
                offset=offset,
            )

    async def search_with_query(
        self,
        search_query: SearchQuery,
        user_id: UUID,
    ) -> SearchResults:
        """Execute a search using a SearchQuery schema.

        Convenience method that accepts a SearchQuery pydantic model
        instead of individual parameters.

        Args:
            search_query: SearchQuery schema with query parameters.
            user_id: UUID of the requesting user.

        Returns:
            SearchResults containing matching notes.
        """
        return await self.search(
            query=search_query.query,
            user_id=user_id,
            limit=search_query.limit,
            offset=search_query.offset,
        )
