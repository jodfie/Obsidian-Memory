"""Supabase OAuth authentication middleware for FastAPI."""

import ipaddress
import os
import time
from typing import Callable

import httpx
import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

# Trusted internal networks (Docker internal networks)
# These bypass Supabase auth and use regular Bearer token auth instead
TRUSTED_INTERNAL_NETWORKS = [
    ipaddress.ip_network("172.16.0.0/12"),  # Docker default bridge networks
    ipaddress.ip_network("10.0.0.0/8"),  # Private network range A
    ipaddress.ip_network("192.168.0.0/16"),  # Private network range C
    ipaddress.ip_network("127.0.0.0/8"),  # Localhost
]

# Environment variable to disable internal bypass (for testing)
DISABLE_INTERNAL_BYPASS = os.getenv("DISABLE_INTERNAL_BYPASS", "false").lower() == "true"


def is_trusted_internal_request(request: Request) -> bool:
    """Check if request comes from a trusted internal network.

    Args:
        request: FastAPI request object

    Returns:
        True if request is from trusted internal network
    """
    if DISABLE_INTERNAL_BYPASS:
        return False

    # Get client IP from request
    client_host = request.client.host if request.client else None
    if not client_host:
        return False

    try:
        client_ip = ipaddress.ip_address(client_host)
        for network in TRUSTED_INTERNAL_NETWORKS:
            if client_ip in network:
                return True
    except ValueError:
        # Invalid IP address format
        pass

    return False


# Cache for Supabase public keys (JWKS)
_public_keys_cache: dict[str, dict] = {}
_cache_expiry: dict[str, float] = {}
CACHE_TTL = 3600  # Cache keys for 1 hour


async def get_supabase_public_keys(supabase_url: str) -> dict[str, dict]:
    """Fetch Supabase public keys (JWKS).

    Args:
        supabase_url: Supabase project URL (e.g., https://xxx.supabase.co)

    Returns:
        Dictionary of key_id -> public key

    Raises:
        HTTPException: If unable to fetch keys
    """
    # Check cache first
    cache_key = f"jwks_{supabase_url}"
    if cache_key in _public_keys_cache:
        if time.time() < _cache_expiry.get(cache_key, 0):
            return _public_keys_cache[cache_key]

    # Fetch JWKS from Supabase
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            jwks = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch Supabase public keys: {str(e)}",
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


async def verify_supabase_jwt(request: Request) -> dict[str, str] | None:
    """Verify Supabase JWT token.

    Args:
        request: FastAPI request

    Returns:
        User identity information if valid, None otherwise

    Raises:
        HTTPException: If token is invalid or missing
    """
    from app.config import settings

    # If Supabase auth is not enabled, skip verification
    if not getattr(settings, 'supabase_auth_enabled', False):
        return None

    # Extract JWT from Authorization header
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_token = auth_header[7:]  # Remove 'Bearer ' prefix

    # Get Supabase URL
    supabase_url = getattr(settings, 'supabase_url', None)
    if not supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase URL not configured",
        )

    try:
        # Decode JWT header to get key ID (kid)
        try:
            unverified_header = jwt.get_unverified_header(jwt_token)
        except jwt.exceptions.DecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid JWT format: {str(e)}",
            )
        
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="JWT missing key ID (kid) in header",
            )

        # Fetch public keys
        public_keys = await get_supabase_public_keys(supabase_url)
        if kid not in public_keys:
            raise ValueError(f"Public key with kid '{kid}' not found in JWKS")

        # Get the public key
        jwk = public_keys[kid]

        # Verify JWT signature, expiration, and claims
        # Supabase JWTs have iss = https://xxx.supabase.co/auth/v1
        expected_issuer = f"{supabase_url}/auth/v1"

        # For Supabase, we verify against the JWT secret or use JWKS
        # Using JWKS verification (RS256)
        import json
        payload = jwt.decode(
            jwt_token,
            jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk)),
            algorithms=["RS256"],
            issuer=expected_issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
            },
        )

        # Extract user identity
        # Supabase JWTs contain 'sub' (user ID) and 'email'
        user_id = payload.get('sub', 'unknown')
        email = payload.get('email', '')
        
        return {
            'user_id': user_id,
            'email': email,
            'iss': payload.get('iss', ''),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token verification failed: {str(e)}",
        )


async def supabase_auth_middleware(request: Request, call_next: Callable):
    """Supabase authentication middleware.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response from next handler
    """
    # Skip auth for OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)

    # Skip Supabase auth for trusted internal network requests
    # These will still go through regular Bearer token auth if configured
    if is_trusted_internal_request(request):
        return await call_next(request)

    # Skip auth for public endpoints
    skip_paths = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]
    
    if request.url.path in skip_paths:
        return await call_next(request)

    # Verify Supabase JWT
    try:
        identity = await verify_supabase_jwt(request)
        if identity:
            # Attach identity to request state for use in endpoints
            request.state.supabase_identity = identity
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail},
            headers=e.headers or {},
        )

    return await call_next(request)
