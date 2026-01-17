"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.graph import router as graph_router
from app.api.notes import router as notes_router
from app.api.projects import router as projects_router
from app.api.sessions import router as sessions_router
from app.config import settings

app = FastAPI(
    title=settings.api_title,
    description="Unified memory management system for Claude Code",
    version=settings.api_version,
    debug=settings.debug,
)

# Include routers
app.include_router(notes_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(graph_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Obsidian-Memory API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
