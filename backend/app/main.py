"""FastAPI application entry point."""

from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.graph import router as graph_router
from app.api.mcp import router as mcp_router
from app.api.notes import router as notes_router
from app.api.projects import router as projects_router
from app.api.sessions import router as sessions_router
from app.api.sync import router as sync_router
from app.api.vaults import router as vaults_router
from app.config import settings
from app.middleware.auth import auth_middleware
from app.middleware.cloudflare_access import cloudflare_access_middleware
from app.middleware.compression import compression_middleware
from app.middleware.error_handler import error_handler_middleware
from app.middleware.logging import logging_middleware
from app.middleware.rate_limiter import rate_limit_middleware
from app.middleware.request_validation import request_validation_middleware
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

# Add CORS middleware if enabled
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "CF-Access-JWT",
            "Mcp-Session-Id",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
            "Mcp-Session-Id",
        ],
    )

# Add compression middleware (before logging to compress responses)
app.add_middleware(BaseHTTPMiddleware, dispatch=compression_middleware)

# Add logging middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# Add rate limiting middleware
if settings.rate_limit_enabled:
    app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

# Add request validation middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=request_validation_middleware)

# Add Cloudflare Access middleware if enabled (runs before Bearer token auth)
if settings.cloudflare_access_enabled:
    app.add_middleware(BaseHTTPMiddleware, dispatch=cloudflare_access_middleware)

# Add Bearer token authentication middleware if enabled
if settings.require_auth:
    app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# Include routers
app.include_router(vaults_router)
app.include_router(notes_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(graph_router)
app.include_router(sync_router)
app.include_router(mcp_router)  # MCP server proxy (OAuth handled by gateway)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Obsidian-Memory API"}


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint with detailed status.

    Returns:
        Health status with version and vault connection info
    """
    from app.api.dependencies import get_vault_manager
    from app.config import settings
    
    # Check vault connection
    vault_connected = False
    try:
        from app.services.vault_manager import VaultManager
        from app.models.vault import VaultManagerConfig
        
        config_file = settings.config_file
        if config_file.exists():
            import json
            with open(config_file, encoding="utf-8") as f:
                data = json.load(f)
            config = VaultManagerConfig(**data)
            vault_manager = VaultManager(config)
            vault_connected = len(vault_manager.vaults) > 0
    except Exception:
        vault_connected = False
    
    return {
        "status": "healthy",
        "version": settings.api_version,
        "vault_connected": vault_connected,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
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
