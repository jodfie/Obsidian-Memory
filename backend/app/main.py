"""FastAPI application entry point."""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.graph import router as graph_router
from app.api.notes import router as notes_router
from app.api.projects import router as projects_router
from app.api.sessions import router as sessions_router
from app.api.sync import router as sync_router
from app.config import settings
from app.middleware.auth import auth_middleware
from app.middleware.cloudflare_access import cloudflare_access_middleware
from app.middleware.error_handler import error_handler_middleware
from app.middleware.logging import logging_middleware
from app.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.api_title,
    description="Unified memory management system for Claude Code",
    version=settings.api_version,
    debug=settings.debug,
)

# Add error handler middleware first (outermost)
app.add_middleware(BaseHTTPMiddleware, dispatch=error_handler_middleware)

# Add logging middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# Add Cloudflare Access middleware if enabled (runs before Bearer token auth)
if settings.cloudflare_access_enabled:
    app.add_middleware(BaseHTTPMiddleware, dispatch=cloudflare_access_middleware)

# Add Bearer token authentication middleware if enabled
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


@app.get("/metrics")
async def metrics() -> dict[str, any]:
    """Metrics endpoint for monitoring.

    Returns:
        Dictionary with application metrics
    """
    try:
        import psutil
        import os

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            "status": "ok",
            "memory": {
                "rss": memory_info.rss,
                "vms": memory_info.vms,
                "percent": process.memory_percent(),
            },
            "cpu": {
                "percent": process.cpu_percent(interval=0.1),
            },
            "threads": process.num_threads(),
        }
    except ImportError:
        logger.warning("psutil not available, returning basic metrics")
        return {
            "status": "ok",
            "message": "psutil not available for detailed metrics",
        }
