"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Obsidian-Memory",
    description="Unified memory management system for Claude Code",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Obsidian-Memory API"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
