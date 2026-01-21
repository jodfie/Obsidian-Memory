"""MCP server proxy endpoint for remote access."""

import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse, StreamingResponse

router = APIRouter(prefix="/mcp", tags=["mcp"])

# OAuth router at root level for Claude.ai compatibility
oauth_router = APIRouter(tags=["oauth"])

# MCP server URL (internal Docker network)
# Use environment variable or default based on environment
# Service name in docker-compose is 'mcp-server'
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:3000")


@router.get("/sse")
@router.get("/sse/")
async def mcp_sse_proxy(request: Request):
    """Proxy SSE connection to MCP server.

    This endpoint allows Claude.ai and other clients to connect to the MCP server
    via Server-Sent Events through Cloudflare Access authentication.
    """
    # Create headers for upstream request
    upstream_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ["host", "content-length"]
    }

    async def event_generator():
        """Generator that manages its own httpx client lifecycle."""
        # Use a long timeout for SSE connections
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            try:
                async with client.stream(
                    "GET",
                    f"{MCP_SERVER_URL}/sse",
                    headers=upstream_headers,
                ) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.RequestError:
                # Connection closed or error - just end the stream
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )


@router.post("/message")
@router.post("/message/")
async def mcp_message_proxy(request: Request):
    """Proxy JSON-RPC messages to MCP server."""
    body = await request.body()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{MCP_SERVER_URL}/message",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **{
                        key: value
                        for key, value in request.headers.items()
                        if key.lower() in ["authorization", "cf-access-jwt"]
                    },
                },
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                },
            )
        except httpx.RequestError as e:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MCP server unavailable: {str(e)}",
            )


@router.get("/health")
@router.get("/health/")
async def mcp_health_proxy():
    """Proxy health check to MCP server."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{MCP_SERVER_URL}/health")
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except httpx.RequestError:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP server unavailable",
            )


@router.options("/{path:path}")
async def mcp_options(path: str):
    """Handle CORS preflight requests."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, CF-Access-JWT",
            "Access-Control-Max-Age": "3600",
        },
    )


# =============================================================================
# OAuth 2.0 Endpoints for Claude.ai MCP Integration
# =============================================================================
# These endpoints proxy OAuth requests to Cloudflare Access OIDC provider

# OAuth configuration from environment
CLOUDFLARE_TEAM_DOMAIN = os.getenv(
    "CLOUDFLARE_ACCESS_TEAM_DOMAIN", "redleif.cloudflareaccess.com"
)
CLOUDFLARE_OAUTH_CLIENT_ID = os.getenv("CLOUDFLARE_OAUTH_CLIENT_ID", "")
CLOUDFLARE_OAUTH_CLIENT_SECRET = os.getenv("CLOUDFLARE_OAUTH_CLIENT_SECRET", "")

# Derive Cloudflare OIDC endpoints
CF_AUTH_ENDPOINT = (
    f"https://{CLOUDFLARE_TEAM_DOMAIN}/cdn-cgi/access/sso/oidc/"
    f"{CLOUDFLARE_OAUTH_CLIENT_ID}/authorization"
)
CF_TOKEN_ENDPOINT = (
    f"https://{CLOUDFLARE_TEAM_DOMAIN}/cdn-cgi/access/sso/oidc/"
    f"{CLOUDFLARE_OAUTH_CLIENT_ID}/token"
)
CF_USERINFO_ENDPOINT = (
    f"https://{CLOUDFLARE_TEAM_DOMAIN}/cdn-cgi/access/sso/oidc/"
    f"{CLOUDFLARE_OAUTH_CLIENT_ID}/userinfo"
)
CF_JWKS_URI = f"https://{CLOUDFLARE_TEAM_DOMAIN}/cdn-cgi/access/certs"


@oauth_router.get("/authorize")
async def oauth_authorize(request: Request):
    """OAuth 2.0 Authorization Endpoint - redirects to Cloudflare Access."""
    # Build Cloudflare authorization URL with all query params
    params = dict(request.query_params)

    # Ensure client_id is set
    if "client_id" not in params and CLOUDFLARE_OAUTH_CLIENT_ID:
        params["client_id"] = CLOUDFLARE_OAUTH_CLIENT_ID

    cf_auth_url = f"{CF_AUTH_ENDPOINT}?{urlencode(params)}"

    return RedirectResponse(url=cf_auth_url, status_code=302)


@oauth_router.post("/token")
async def oauth_token(request: Request):
    """OAuth 2.0 Token Endpoint - proxies to Cloudflare Access."""
    content_type = request.headers.get("content-type", "")

    # Parse request body
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        params = dict(form_data)
    elif "application/json" in content_type:
        json_data = await request.json()
        params = dict(json_data)
    else:
        body = await request.body()
        params = dict(x.split("=") for x in body.decode().split("&") if "=" in x)

    # Add client credentials if not present
    if "client_id" not in params and CLOUDFLARE_OAUTH_CLIENT_ID:
        params["client_id"] = CLOUDFLARE_OAUTH_CLIENT_ID
    if "client_secret" not in params and CLOUDFLARE_OAUTH_CLIENT_SECRET:
        params["client_secret"] = CLOUDFLARE_OAUTH_CLIENT_SECRET

    # Proxy to Cloudflare token endpoint
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                CF_TOKEN_ENDPOINT,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except httpx.RequestError as e:
            return Response(
                content=f'{{"error": "server_error", "error_description": "{str(e)}"}}',
                status_code=500,
                headers={"Content-Type": "application/json"},
            )


@oauth_router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request):
    """OAuth 2.0 Authorization Server Metadata."""
    # Determine server URL from request, respecting X-Forwarded-Proto header
    proto = request.headers.get("X-Forwarded-Proto", "http")
    host = request.headers.get("Host", request.url.hostname or "localhost")
    server_url = f"{proto}://{host}"

    metadata = {
        "issuer": server_url,
        "authorization_endpoint": f"{server_url}/authorize",
        "token_endpoint": f"{server_url}/token",
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
        ],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
        "scopes_supported": ["openid", "email", "profile"],
        "code_challenge_methods_supported": ["S256"],
        "jwks_uri": CF_JWKS_URI,
    }

    return Response(
        content=__import__("json").dumps(metadata, indent=2),
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
    )


@oauth_router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request):
    """OpenID Connect Discovery Endpoint."""
    # Determine server URL from request, respecting X-Forwarded-Proto header
    proto = request.headers.get("X-Forwarded-Proto", "http")
    host = request.headers.get("Host", request.url.hostname or "localhost")
    server_url = f"{proto}://{host}"

    config = {
        "issuer": f"https://{CLOUDFLARE_TEAM_DOMAIN}",
        "authorization_endpoint": f"{server_url}/authorize",
        "token_endpoint": f"{server_url}/token",
        "userinfo_endpoint": CF_USERINFO_ENDPOINT,
        "jwks_uri": CF_JWKS_URI,
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "email", "profile"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
        ],
        "claims_supported": ["sub", "email", "name", "preferred_username"],
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
    }

    return Response(
        content=__import__("json").dumps(config, indent=2),
        status_code=200,
        headers={
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
    )


@oauth_router.options("/authorize")
@oauth_router.options("/token")
@oauth_router.options("/.well-known/oauth-authorization-server")
@oauth_router.options("/.well-known/openid-configuration")
async def oauth_options():
    """Handle CORS preflight for OAuth endpoints."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        },
    )


# =============================================================================
# Root-Level MCP Endpoints for Claude.ai Compatibility
# =============================================================================
# Claude.ai expects /sse and /message at root level, not under /mcp prefix


@oauth_router.get("/sse")
@oauth_router.get("/sse/")
async def root_sse_proxy(request: Request):
    """Root-level SSE endpoint for Claude.ai MCP compatibility.

    Proxies to internal MCP server. Requires Bearer token authentication.
    """
    upstream_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ["host", "content-length"]
    }

    async def event_generator():
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            try:
                async with client.stream(
                    "GET",
                    f"{MCP_SERVER_URL}/sse",
                    headers=upstream_headers,
                ) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.RequestError:
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )


@oauth_router.post("/message")
@oauth_router.post("/message/")
async def root_message_proxy(request: Request):
    """Root-level message endpoint for Claude.ai MCP compatibility.

    Proxies JSON-RPC messages to internal MCP server. Requires Bearer token authentication.
    """
    body = await request.body()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{MCP_SERVER_URL}/message",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    **{
                        key: value
                        for key, value in request.headers.items()
                        if key.lower() in ["authorization", "cf-access-jwt"]
                    },
                },
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                },
            )
        except httpx.RequestError as e:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MCP server unavailable: {str(e)}",
            )


@oauth_router.options("/sse")
@oauth_router.options("/message")
async def mcp_root_options():
    """Handle CORS preflight for root-level MCP endpoints."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, CF-Access-JWT",
            "Access-Control-Max-Age": "3600",
        },
    )
