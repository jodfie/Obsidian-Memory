"""Async database session management with dual-mode SQLite/Postgres support.

This module provides async SQLAlchemy engine and session management that can switch
between SQLite (for local development) and Postgres (for Supabase production).

Usage:
    from app.db import get_db, get_async_engine

    # In FastAPI dependency injection:
    @app.get("/items")
    async def get_items(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(ItemModel))
        return result.scalars().all()

Environment Variables:
    DB_MODE: "sqlite" (default) or "postgres"
    DATABASE_URL: Full connection URL (optional, auto-generated if not set)
    SQLITE_DB_PATH: Path for SQLite file (default: ~/.obsidian-memory/obsidian_memory.db)
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import DatabaseMode, settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

# Module-level engine cache to ensure single engine instance
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _build_database_url() -> str:
    """Build the database URL based on configuration.

    Returns:
        Async-compatible database URL string.

    Raises:
        ValueError: If configuration is invalid for the selected mode.
    """
    # If explicit database_url is provided, use it
    if settings.database_url:
        url = settings.database_url
        # Ensure async driver prefix for common URL formats
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("sqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    # Build URL from mode-specific settings
    if settings.db_mode == DatabaseMode.SQLITE:
        # Ensure parent directory exists
        settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{settings.sqlite_db_path}"

    elif settings.db_mode == DatabaseMode.POSTGRES:
        # For Postgres mode, we need either database_url or supabase_url
        if settings.supabase_url:
            # Extract connection info from Supabase URL
            # Supabase direct connection: postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
            # Note: User must set DATABASE_URL for direct DB access; supabase_url is for API
            raise ValueError(
                "For Postgres mode, set DATABASE_URL with your Supabase direct connection string. "
                "Format: postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"
            )
        raise ValueError(
            "Postgres mode requires DATABASE_URL to be set. "
            "Get your connection string from Supabase Dashboard > Settings > Database."
        )

    raise ValueError(f"Unknown database mode: {settings.db_mode}")


def get_async_engine() -> AsyncEngine:
    """Get or create the async SQLAlchemy engine.

    This function implements a singleton pattern - the engine is created once
    and reused for all subsequent calls. This ensures connection pooling works
    correctly and avoids creating multiple engines.

    Returns:
        AsyncEngine: The SQLAlchemy async engine instance.

    Raises:
        ValueError: If database configuration is invalid.
    """
    global _engine

    if _engine is None:
        database_url = _build_database_url()

        # Engine configuration varies by database type
        if settings.db_mode == DatabaseMode.SQLITE:
            # SQLite-specific settings
            _engine = create_async_engine(
                database_url,
                echo=settings.debug,
                # SQLite doesn't use connection pooling the same way
                pool_pre_ping=False,
                # Important for async SQLite
                connect_args={"check_same_thread": False},
            )
        else:
            # Postgres-specific settings with connection pooling
            _engine = create_async_engine(
                database_url,
                echo=settings.debug,
                # Connection pool settings for production
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,  # Recycle connections after 30 minutes
                pool_pre_ping=True,  # Verify connections before use
            )

    return _engine


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session maker.

    Returns:
        async_sessionmaker: Factory for creating AsyncSession instances.
    """
    global _async_session_maker

    if _async_session_maker is None:
        engine = get_async_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Prevent lazy loading issues after commit
            autocommit=False,
            autoflush=False,
        )

    return _async_session_maker


# Alias for backward compatibility and cleaner imports
AsyncSessionLocal = get_async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    This is the primary way to get a database session in FastAPI endpoints.
    The session is automatically closed when the request completes.

    Yields:
        AsyncSession: A SQLAlchemy async session.

    Example:
        @app.get("/notes")
        async def list_notes(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(NoteModel))
            return result.scalars().all()
    """
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables.

    This should be called during application startup to ensure
    all SQLAlchemy models have their tables created.

    Note: In production with Postgres/Supabase, migrations should be
    handled separately (e.g., via Supabase migrations or Alembic).
    """
    from app.models.db_models import Base

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the database engine and cleanup connections.

    This should be called during application shutdown to ensure
    all connections are properly closed.
    """
    global _engine, _async_session_maker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
