"""API v1 module - Versioned API endpoints.

This module contains all v1 API endpoints with proper versioning
and comprehensive OpenAPI documentation.
"""

from fastapi import APIRouter

# Import v1 routers (only notes router exists currently)
from app.api.v1.notes import router as notes_router

# TODO: Import these routers once created:
# from app.api.v1.vaults import router as vaults_router
# from app.api.v1.projects import router as projects_router
# from app.api.v1.sessions import router as sessions_router
# from app.api.v1.graph import router as graph_router
# from app.api.v1.sync import router as sync_router

# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include implemented routers
router.include_router(notes_router)

# TODO: Include these routers once created:
# router.include_router(vaults_router)
# router.include_router(projects_router)
# router.include_router(sessions_router)
# router.include_router(graph_router)
# router.include_router(sync_router)

__all__ = ["router"]