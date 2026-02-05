"""API v1 module - Versioned API endpoints.

This module contains all v1 API endpoints with proper versioning
and comprehensive OpenAPI documentation.

The API supports two modes:
1. File-based: Traditional vault operations using markdown files (notes.py)
2. Postgres-backed: Database-driven operations using Supabase (notes_pg.py, graph_pg.py)

The Postgres-backed endpoints are the recommended approach for production
deployments with Supabase/ElectricSQL.
"""

from fastapi import APIRouter

# Import file-based v1 routers (legacy/local mode)
from app.api.v1.notes import router as notes_file_router

# Import Postgres-backed v1 routers (Supabase mode)
from app.api.v1.notes_pg import router as notes_pg_router
from app.api.v1.graph_pg import router as graph_pg_router

# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include file-based routers (prefix with /file for disambiguation)
# These use the traditional VaultManager with markdown files
file_router = APIRouter(prefix="/file", tags=["File-Based Operations"])
file_router.include_router(notes_file_router)

# Include Postgres-backed routers (prefix with /pg for database operations)
# These use PostgresVaultManager, PostgresSearchIndex, and PostgresGraphEngine
pg_router = APIRouter(prefix="/pg", tags=["Postgres-Backed Operations"])
pg_router.include_router(notes_pg_router)
pg_router.include_router(graph_pg_router)

# Add both router groups to the main v1 router
router.include_router(file_router)
router.include_router(pg_router)

__all__ = ["router"]
