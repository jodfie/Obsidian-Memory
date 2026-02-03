"""Authentication middleware for FastAPI."""

from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


async def verify_token(credentials: HTTPAuthorizationCredentials | None) -> bool:
    """Verify Bearer token.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        True if token is valid

    Raises:
        HTTPException: If token is invalid or missing
    """
    from app.config import settings

    # If no token required in settings, allow all requests
    if not getattr(settings, 'require_auth', False):
        return True

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Get expected token from settings
    expected_token = getattr(settings, 'api_token', None)

    if not expected_token:
        # No token configured, allow all (development mode)
        return True

    # Verify token matches
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication token",
        )

    return True


async def auth_middleware(request: Request, call_next: Callable):
    """Authentication middleware.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response from next handler
    """
    from fastapi.responses import JSONResponse

    # Skip auth for health check, docs, and OAuth endpoints
    skip_paths = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        # OAuth endpoints must be public for OAuth flow
        "/authorize",
        "/token",
        "/.well-known/oauth-authorization-server",
        "/.well-known/openid-configuration",
        "/.well-known/oauth-protected-resource",
        # MCP OAuth endpoints
        "/mcp/authorize",
        "/mcp/token",
        "/mcp/.well-known/oauth-authorization-server",
        "/mcp/.well-known/openid-configuration",
        "/mcp/.well-known/oauth-protected-resource",
    ]
    if request.url.path in skip_paths:
        return await call_next(request)

    # Extract Bearer token
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    else:
        credentials = None

    # Verify token
    try:
        await verify_token(credentials)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail},
            headers=e.headers,
        )

    return await call_next(request)
