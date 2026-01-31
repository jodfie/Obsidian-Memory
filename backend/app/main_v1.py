"""FastAPI application with API versioning and enhanced OpenAPI documentation."""

import time
from datetime import datetime
from typing import Any, Callable, List

from fastapi import FastAPI, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware

# Import v1 API router
from app.api.v1 import router as v1_router

# Import legacy routers (will be deprecated)
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
from app.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Custom OpenAPI schema generation
def custom_openapi():
    """Generate custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Obsidian-Memory API",
        version="1.0.0",
        description="""
# Obsidian-Memory API Documentation

Unified memory management system for Claude Code with comprehensive note management,
knowledge graph, and search capabilities.

## Features

- **Note Management**: CRUD operations for markdown notes with metadata
- **Knowledge Graph**: Traverse relationships between notes
- **Full-text Search**: Advanced search with FTS5 support
- **Project Organization**: Group notes by projects
- **Session Tracking**: Track and analyze work sessions
- **Vault Management**: Multi-vault support with isolation
- **Sync Operations**: Synchronize notes across vaults

## Authentication

The API supports two authentication methods:

### 1. Cloudflare Access (Browser-based)
- JWT tokens via `CF-Access-JWT` header
- Automatic for browser-based access through Cloudflare Zero Trust

### 2. OAuth Bearer Tokens (API Access)
- Bearer tokens via `Authorization: Bearer <token>` header
- Used for programmatic access and Claude.ai MCP integration

### Internal Network Bypass
Requests from trusted internal networks (Docker, private ranges) can bypass
Cloudflare Access authentication if configured.

## API Versioning

All endpoints are versioned under `/api/v1/` prefix. Legacy endpoints at `/api/`
are deprecated and will be removed in v2.0.0.

## Rate Limiting

- Default: 100 requests per minute per IP
- Authenticated: 1000 requests per minute per user
- Burst allowance: 2x the limit for short periods

## Error Responses

All errors follow a consistent format:
```json
{
    "detail": "Error message describing what went wrong",
    "code": "ERROR_CODE"  // Optional error code for client handling
}
```

## Pagination

List endpoints support pagination via `limit` and `offset` parameters:
- `limit`: Maximum items to return (max: 500)
- `offset`: Number of items to skip
- Response includes `total` count and `has_more` flag

## Examples

See individual endpoint documentation for request/response examples.
        """,
        openapi_version="3.1.0",
        routes=app.routes,
        tags=[
            {
                "name": "Notes",
                "description": "Note CRUD operations and search",
            },
            {
                "name": "Vaults",
                "description": "Vault management and configuration",
            },
            {
                "name": "Graph",
                "description": "Knowledge graph traversal and analysis",
            },
            {
                "name": "Projects",
                "description": "Project organization and management",
            },
            {
                "name": "Sessions",
                "description": "Session tracking and analysis",
            },
            {
                "name": "Sync",
                "description": "Note synchronization operations",
            },
            {
                "name": "MCP",
                "description": "Model Context Protocol integration",
            },
            {
                "name": "Health",
                "description": "Health checks and monitoring",
            },
        ],
        servers=[
            {
                "url": "http://localhost:8000",
                "description": "Local development server",
            },
            {
                "url": "https://api.obsidian-memory.com",
                "description": "Production server",
            },
        ],
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "CloudflareAccess": {
            "type": "apiKey",
            "in": "header",
            "name": "CF-Access-JWT",
            "description": "Cloudflare Access JWT token for browser-based authentication",
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "OAuth Bearer token for API access (Claude.ai MCP)",
        },
    }

    # Apply security globally (either auth method is acceptable)
    openapi_schema["security"] = [
        {"CloudflareAccess": []},
        {"BearerAuth": []},
    ]

    # Add example responses for common status codes
    openapi_schema["components"]["responses"] = {
        "UnauthorizedError": {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "string",
                                "example": "Cloudflare Access JWT token required"
                            }
                        }
                    }
                }
            }
        },
        "ForbiddenError": {
            "description": "Invalid authentication",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "string",
                                "example": "Invalid authentication token"
                            }
                        }
                    }
                }
            }
        },
        "NotFoundError": {
            "description": "Resource not found",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "string",
                                "example": "Resource not found"
                            }
                        }
                    }
                }
            }
        },
        "ValidationError": {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "loc": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        },
                                        "msg": {"type": "string"},
                                        "type": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "InternalServerError": {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "detail": {
                                "type": "string",
                                "example": "Internal server error occurred"
                            }
                        }
                    }
                }
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app = FastAPI(
    title=settings.api_title,
    description="Unified memory management system for Claude Code",
    version="1.0.0",  # Semantic versioning
    debug=settings.debug,
    openapi_url="/api/v1/openapi.json",  # Versioned OpenAPI spec
    docs_url="/api/v1/docs",  # Versioned Swagger UI
    redoc_url="/api/v1/redoc",  # Versioned ReDoc
)

# Override OpenAPI schema generation
app.openapi = custom_openapi

# Add error handler middleware first (outermost)
app.add_middleware(BaseHTTPMiddleware, dispatch=error_handler_middleware)

# Add compression middleware (before logging to compress responses)
app.add_middleware(BaseHTTPMiddleware, dispatch=compression_middleware)

# Add logging middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# Add Cloudflare Access middleware if enabled (runs before Bearer token auth)
if settings.cloudflare_access_enabled:
    app.add_middleware(BaseHTTPMiddleware, dispatch=cloudflare_access_middleware)

# Add Bearer token authentication middleware if enabled
if settings.require_auth:
    app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# Include v1 API router
app.include_router(v1_router)

# Include legacy routers (deprecated, will be removed in v2.0.0)
# These are kept for backward compatibility
app.include_router(vaults_router)
app.include_router(notes_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(graph_router)
app.include_router(sync_router)
app.include_router(mcp_router)  # MCP server proxy (OAuth handled by gateway)


@app.get(
    "/",
    tags=["Health"],
    summary="Root endpoint",
    description="Basic API information endpoint",
    responses={
        200: {
            "description": "API information",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Obsidian-Memory API",
                        "version": "1.0.0",
                        "docs": "/api/v1/docs"
                    }
                }
            }
        }
    }
)
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "message": "Obsidian-Memory API",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Comprehensive health check with vault connectivity status",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                        "vault_connected": True,
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
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
        "version": "1.0.0",
        "vault_connected": vault_connected,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get(
    "/api/v1/health",
    tags=["Health"],
    summary="Versioned health check",
    description="Health check endpoint for v1 API",
    responses={
        200: {
            "description": "Service is healthy",
        }
    }
)
async def health_v1() -> dict[str, Any]:
    """Versioned health check endpoint."""
    return await health()


@app.get(
    "/metrics",
    tags=["Health"],
    summary="Metrics endpoint",
    description="Application metrics for monitoring and observability",
    responses={
        200: {
            "description": "Metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "memory": {
                            "rss": 104857600,
                            "vms": 209715200,
                            "percent": 2.5
                        },
                        "cpu": {
                            "percent": 15.2
                        },
                        "threads": 4
                    }
                }
            }
        }
    }
)
async def metrics() -> dict[str, Any]:
    """Metrics endpoint for monitoring.

    Returns:
        Dictionary with application metrics including:
        - Memory usage (RSS, VMS, percentage)
        - CPU usage percentage
        - Thread count
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