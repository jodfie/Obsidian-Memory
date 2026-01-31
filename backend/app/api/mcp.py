"""MCP server proxy endpoint for remote access.

Note: OAuth/authentication is handled by the external OAuth gateway (Traefik ForwardAuth).
This module only handles MCP protocol proxying to the internal MCP server.
"""

import os

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/mcp", tags=["mcp"])

# MCP server URL (internal Docker network)
# Use environment variable or default based on environment
# Service name in docker-compose is 'mcp-server'
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:3000")


@router.get("/sse")
@router.get("/sse/")
async def mcp_sse_proxy(request: Request):
    """Proxy SSE connection to MCP server.

    This endpoint allows clients to connect to the MCP server
    via Server-Sent Events. Authentication is handled by the OAuth gateway.
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


@router.post("")
@router.post("/")
async def mcp_streamable_http_proxy(request: Request):
    """Proxy Streamable HTTP requests to MCP server.

    This handles the MCP 2025-03-26 Streamable HTTP transport.
    Supports both single JSON-RPC requests and SSE streaming responses.
    """
    body = await request.body()

    # Forward headers that matter, including MCP session ID
    upstream_headers = {
        "Content-Type": request.headers.get("content-type", "application/json"),
        **{
            key: value
            for key, value in request.headers.items()
            if key.lower() in ["authorization", "cf-access-jwt", "accept", "mcp-session-id"]
        },
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        try:
            response = await client.post(
                f"{MCP_SERVER_URL}/mcp",
                content=body,
                headers=upstream_headers,
            )

            # Check if response is SSE (streaming)
            content_type = response.headers.get("content-type", "")

            # Build response headers, forwarding MCP session ID
            response_headers = {
                "Content-Type": content_type or "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Mcp-Session-Id",
                "Access-Control-Expose-Headers": "Mcp-Session-Id",
            }

            # Forward Mcp-Session-Id from upstream response
            session_id = response.headers.get("mcp-session-id")
            if session_id:
                response_headers["Mcp-Session-Id"] = session_id

            if "text/event-stream" in content_type:
                # For SSE responses, we need to stream
                async def stream_response():
                    async with client.stream(
                        "POST",
                        f"{MCP_SERVER_URL}/mcp",
                        content=body,
                        headers=upstream_headers,
                    ) as stream_resp:
                        async for chunk in stream_resp.aiter_bytes():
                            yield chunk

                return StreamingResponse(
                    stream_response(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Expose-Headers": "Mcp-Session-Id",
                        **({"Mcp-Session-Id": session_id} if session_id else {}),
                    },
                )

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
            )
        except httpx.RequestError as e:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MCP server unavailable: {str(e)}",
            )


@router.get("")
@router.get("/")
async def mcp_streamable_http_get_proxy(request: Request):
    """Proxy GET requests to MCP server for SSE streaming."""
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
                    f"{MCP_SERVER_URL}/mcp",
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
        },
    )


@router.delete("")
@router.delete("/")
async def mcp_streamable_http_delete_proxy(request: Request):
    """Proxy DELETE requests to MCP server for session termination."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.delete(
                f"{MCP_SERVER_URL}/mcp",
                headers={
                    key: value
                    for key, value in request.headers.items()
                    if key.lower() in ["authorization", "cf-access-jwt", "mcp-session-id"]
                },
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except httpx.RequestError:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP server unavailable",
            )


@router.options("")
@router.options("/")
@router.options("/{path:path}")
async def mcp_options(path: str = ""):
    """Handle CORS preflight requests."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, CF-Access-JWT, Mcp-Session-Id",
            "Access-Control-Max-Age": "3600",
        },
    )
