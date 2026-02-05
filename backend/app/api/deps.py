"""API dependencies for FastAPI endpoints.

This module provides dependency injection for the Postgres-backed services
used by the v1 API endpoints.
"""

from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.graph_engine_pg import PostgresGraphEngine
from app.services.search_index_pg import PostgresSearchIndex
from app.services.vault_manager_pg import PostgresVaultManager


async def get_vault_manager_pg(
    db: AsyncSession = Depends(get_db),
) -> PostgresVaultManager:
    """Get PostgresVaultManager instance.

    This dependency provides a vault manager backed by Postgres/Supabase
    for note CRUD operations.

    Args:
        db: Async database session from get_db dependency.

    Returns:
        PostgresVaultManager instance.
    """
    return PostgresVaultManager(db)


async def get_search_index_pg(
    db: AsyncSession = Depends(get_db),
) -> PostgresSearchIndex:
    """Get PostgresSearchIndex instance.

    This dependency provides full-text search capabilities using
    Postgres tsvector/tsquery.

    Args:
        db: Async database session from get_db dependency.

    Returns:
        PostgresSearchIndex instance.
    """
    return PostgresSearchIndex(db)


async def get_graph_engine_pg(
    db: AsyncSession = Depends(get_db),
) -> PostgresGraphEngine:
    """Get PostgresGraphEngine instance.

    This dependency provides graph traversal operations for the
    knowledge graph stored in the relations table.

    Args:
        db: Async database session from get_db dependency.

    Returns:
        PostgresGraphEngine instance.
    """
    return PostgresGraphEngine(db)


async def get_current_user_id(
    x_user_id: str | None = Header(None, alias="X-User-ID"),
    authorization: str | None = Header(None),
) -> UUID:
    """Extract the current user ID from request headers.

    This is a placeholder implementation that supports:
    1. X-User-ID header for testing/development
    2. JWT token extraction (to be implemented with actual JWT validation)
    3. Falls back to a test UUID in development

    In production, this should be replaced with proper JWT validation
    from Supabase Auth or your authentication provider.

    Args:
        x_user_id: Optional user ID header (for testing).
        authorization: Optional Authorization header with Bearer token.

    Returns:
        UUID of the authenticated user.

    Raises:
        HTTPException: If authentication fails or no user ID can be determined.
    """
    # Check for explicit X-User-ID header (useful for testing)
    if x_user_id:
        try:
            return UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-User-ID header: must be a valid UUID",
            )

    # TODO: Implement JWT token validation
    # If authorization header is present, extract user_id from JWT claims
    # Example with Supabase:
    #   if authorization and authorization.startswith("Bearer "):
    #       token = authorization.split(" ", 1)[1]
    #       payload = decode_jwt(token)  # Validate with Supabase JWT secret
    #       return UUID(payload["sub"])

    # Development fallback: use a test user ID
    # This should be disabled in production
    # WARNING: This is insecure and only for development/testing
    import os

    if os.environ.get("ENVIRONMENT", "development") == "development":
        # Return a fixed test user ID for development
        test_user_id = os.environ.get(
            "TEST_USER_ID", "00000000-0000-0000-0000-000000000001"
        )
        return UUID(test_user_id)

    # In production, require authentication
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
