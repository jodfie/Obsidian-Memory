"""Cloudflare Access authentication middleware for FastAPI."""

import json
from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


async def verify_cloudflare_access(request: Request) -> dict[str, str] | None:
    """Verify Cloudflare Access JWT token.

    Args:
        request: FastAPI request

    Returns:
        User identity information if valid, None otherwise

    Raises:
        HTTPException: If token is invalid or missing
    """
    from app.config import settings

    # If Cloudflare Access is not enabled, skip verification
    if not getattr(settings, 'cloudflare_access_enabled', False):
        return None

    # Extract JWT from CF-Access-JWT header
    jwt_token = request.headers.get('CF-Access-JWT', None)
    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cloudflare Access JWT token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In a real implementation, you would:
    # 1. Verify the JWT signature using Cloudflare's public keys
    # 2. Check the token expiration
    # 3. Validate the audience and issuer
    # 4. Extract user identity from the token claims

    # For now, we'll do basic validation
    # In production, use a JWT library like PyJWT with Cloudflare's public keys
    try:
        # Placeholder: Parse JWT (without verification for now)
        # In production, verify with: https://<your-team-domain>.cloudflareaccess.com/cdn-cgi/access/certs
        parts = jwt_token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        # Decode payload (base64url)
        import base64
        payload = json.loads(
            base64.urlsafe_b64decode(parts[1] + '==').decode('utf-8')
        )

        # Extract user identity
        email = payload.get('email', payload.get('sub', 'unknown'))
        return {
            'email': email,
            'aud': payload.get('aud', ''),
            'iss': payload.get('iss', ''),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid Cloudflare Access token: {str(e)}",
        )


async def cloudflare_access_middleware(request: Request, call_next: Callable):
    """Cloudflare Access authentication middleware.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response from next handler
    """
    # Skip auth for health check and docs
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)

    # Verify Cloudflare Access token
    try:
        identity = await verify_cloudflare_access(request)
        if identity:
            # Attach identity to request state for use in endpoints
            request.state.cloudflare_identity = identity
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail},
            headers=e.headers,
        )

    return await call_next(request)
