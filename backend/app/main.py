"""FastAPI application entry point."""

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.graph import router as graph_router
from app.api.notes import router as notes_router
from app.api.projects import router as projects_router
from app.api.sessions import router as sessions_router
from app.api.sync import router as sync_router
from app.config import settings
from app.middleware.auth import auth_middleware

app = FastAPI(
    title=settings.api_title,
    description="Unified memory management system for Claude Code",
    version=settings.api_version,
    debug=settings.debug,
)

# Add authentication middleware if enabled
if settings.require_auth:
    app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# Include routers
app.include_router(notes_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(graph_router)
app.include_router(sync_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Obsidian-Memory API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
