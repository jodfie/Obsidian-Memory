"""Factory function for search index instantiation.

This module provides a factory function that returns the appropriate search index
implementation based on the configured database mode.

Usage:
    from app.config import settings
    from app.db import get_db
    from app.services.search_index_factory import get_search_index, SearchIndexType

    @app.get("/search")
    async def search_notes(
        query: str,
        db: AsyncSession = Depends(get_db),
    ):
        search_index = get_search_index(settings.db_mode, session=db)
        # For Postgres mode, search_index is PostgresSearchIndex
        # For SQLite mode, search_index is SearchIndex
        results = await search_index.search(query, user_id)
        return results
"""

from pathlib import Path
from typing import TYPE_CHECKING, overload

from app.config import DatabaseMode

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.search_index import SearchIndex
    from app.services.search_index_pg import PostgresSearchIndex


@overload
def get_search_index(
    db_mode: DatabaseMode,
    *,
    session: "AsyncSession",
    db_path: None = None,
) -> "PostgresSearchIndex": ...


@overload
def get_search_index(
    db_mode: DatabaseMode,
    *,
    session: None = None,
    db_path: Path,
) -> "SearchIndex": ...


def get_search_index(
    db_mode: DatabaseMode,
    *,
    session: "AsyncSession | None" = None,
    db_path: Path | None = None,
) -> "PostgresSearchIndex | SearchIndex":
    """Get the appropriate search index implementation.

    Returns a PostgresSearchIndex for Postgres mode (Supabase) or a file-based
    SearchIndex (SQLite FTS5) for SQLite mode (local development).

    Args:
        db_mode: The database mode from settings (DatabaseMode.SQLITE or DatabaseMode.POSTGRES).
        session: SQLAlchemy AsyncSession (required for Postgres mode).
        db_path: Path to SQLite database file (required for SQLite mode).

    Returns:
        PostgresSearchIndex for Postgres mode, SearchIndex for SQLite mode.

    Raises:
        ValueError: If required arguments are missing for the selected mode.

    Examples:
        # Postgres mode (Supabase)
        search_index = get_search_index(
            DatabaseMode.POSTGRES,
            session=db_session,
        )
        results = await search_index.search("query", user_id=user.id)

        # SQLite mode (file-based FTS5)
        search_index = get_search_index(
            DatabaseMode.SQLITE,
            db_path=Path("~/.obsidian-memory/index.db"),
        )
        await search_index.initialize()
        results = await search_index.search(SearchQuery(query="test"))
    """
    if db_mode == DatabaseMode.POSTGRES:
        if session is None:
            raise ValueError(
                "Postgres mode requires an AsyncSession. "
                "Pass session=db_session to get_search_index()."
            )

        from app.services.search_index_pg import PostgresSearchIndex

        return PostgresSearchIndex(session)

    elif db_mode == DatabaseMode.SQLITE:
        if db_path is None:
            raise ValueError(
                "SQLite mode requires a database path. "
                "Pass db_path=Path(...) to get_search_index()."
            )

        from app.services.search_index import SearchIndex

        return SearchIndex(db_path)

    else:
        raise ValueError(f"Unknown database mode: {db_mode}")


# Convenience type alias for type hints
SearchIndexType = "PostgresSearchIndex | SearchIndex"
