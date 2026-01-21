"""Cloudflare Access authentication middleware for FastAPI."""

import json
import time
from typing import Callable

import httpx
import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

# Cache for Cloudflare public keys (JWKS)
# Keys are fetched from: https://<team-domain>.cloudflareaccess.com/cdn-cgi/access/certs
_public_keys_cache: dict[str, dict] = {}
_cache_expiry: dict[str, float] = {}
CACHE_TTL = 3600  # Cache keys for 1 hour


async def get_cloudflare_public_keys(team_domain: str) -> dict[str, dict]:
    """Fetch Cloudflare Access public keys (JWKS).

    Args:
        team_domain: Cloudflare Access team domain (e.g., example.cloudflareaccess.com)

    Returns:
        Dictionary of key_id -> public key

    Raises:
        HTTPException: If unable to fetch keys
    """
    # Check cache first
    cache_key = f"jwks_{team_domain}"
    if cache_key in _public_keys_cache:
        if time.time() < _cache_expiry.get(cache_key, 0):
            return _public_keys_cache[cache_key]

    # Fetch JWKS from Cloudflare
    certs_url = f"https://{team_domain}/cdn-cgi/access/certs"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(certs_url)
            response.raise_for_status()
            jwks = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch Cloudflare Access public keys: {str(e)}",
        )

    # Convert JWKS to dictionary keyed by kid (key ID)
    keys_dict: dict[str, dict] = {}
    for key in jwks.get("keys", []):
        kid = key.get("kid")
        if kid:
            keys_dict[kid] = key

    # Cache the keys
    _public_keys_cache[cache_key] = keys_dict
    _cache_expiry[cache_key] = time.time() + CACHE_TTL

    return keys_dict


async def verify_cloudflare_access(request: Request) -> dict[str, str] | None:
    """Verify Cloudflare Access JWT token or OAuth Bearer token.

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

    # Try to extract JWT from multiple sources:
    # 1. CF-Access-JWT header (Cloudflare Access browser-based auth)
    # 2. Authorization: Bearer header (OAuth-based auth for Claude.ai MCP)
    jwt_token = request.headers.get('CF-Access-JWT', None)

    if not jwt_token:
        # Try Authorization header (OAuth Bearer token)
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            jwt_token = auth_header[7:]  # Remove 'Bearer ' prefix

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cloudflare Access JWT token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get team domain
    team_domain = getattr(settings, 'cloudflare_access_team_domain', None)
    if not team_domain:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cloudflare Access team domain not configured",
        )

    try:
        # Decode JWT header to get key ID (kid)
        unverified_header = jwt.get_unverified_header(jwt_token)
        kid = unverified_header.get("kid")
        if not kid:
            raise ValueError("JWT missing key ID (kid) in header")

        # Fetch public keys
        public_keys = await get_cloudflare_public_keys(team_domain)
        if kid not in public_keys:
            raise ValueError(f"Public key with kid '{kid}' not found in JWKS")

        # Get the public key
        jwk = public_keys[kid]

        # Verify JWT signature, expiration, and claims
        # Expected issuer: https://<team-domain>.cloudflareaccess.com
        expected_issuer = f"https://{team_domain}"

        # Audience can be either:
        # 1. Team domain (for CF-Access-JWT from browser auth)
        # 2. OAuth client_id (for OAuth access_token from Claude.ai)
        oauth_client_id = getattr(settings, 'cloudflare_oauth_client_id', None)
        valid_audiences = [team_domain]
        if oauth_client_id:
            valid_audiences.append(oauth_client_id)

        payload = jwt.decode(
            jwt_token,
            jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk)),
            algorithms=["RS256"],
            issuer=expected_issuer,
            audience=valid_audiences,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )

        # Extract user identity
        email = payload.get('email', payload.get('sub', 'unknown'))
        return {
            'email': email,
            'aud': payload.get('aud', ''),
            'iss': payload.get('iss', ''),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cloudflare Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid Cloudflare Access token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cloudflare Access token verification failed: {str(e)}",
        )


async def cloudflare_access_middleware(request: Request, call_next: Callable):
    """Cloudflare Access authentication middleware.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response from next handler
    """
    # Skip auth for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)

    # Skip auth for health check, docs, and OAuth endpoints
    # OAuth endpoints must be public for the OAuth flow to work
    skip_paths = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/authorize",
        "/token",
        "/.well-known/oauth-authorization-server",
        "/.well-known/openid-configuration",
    ]
    if request.url.path in skip_paths:
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
