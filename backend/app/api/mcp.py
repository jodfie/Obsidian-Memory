"""MCP server proxy endpoint for remote access."""

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
    
    This endpoint allows Claude.ai and other clients to connect to the MCP server
    via Server-Sent Events through Cloudflare Access authentication.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Forward the request to MCP server
            async with client.stream(
                "GET",
                f"{MCP_SERVER_URL}/sse",
                headers={
                    key: value
                    for key, value in request.headers.items()
                    if key.lower() not in ["host", "content-length"]
                },
            ) as response:
                async def generate():
                    async for chunk in response.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    generate(),
                    status_code=response.status_code,
                    headers={
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
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
