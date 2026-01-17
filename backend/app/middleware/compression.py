"""Response compression middleware."""

import gzip
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


async def compression_middleware(request: Request, call_next: Callable) -> Response:
    """Compress responses with gzip.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Compressed response
    """
    # Check if client accepts gzip
    accept_encoding = request.headers.get("Accept-Encoding", "")
    should_compress = "gzip" in accept_encoding

    response = await call_next(request)

    # Compress response if client supports it and content is compressible
    if should_compress and response.status_code == 200:
        content_type = response.headers.get("Content-Type", "")
        compressible_types = [
            "application/json",
            "text/",
            "application/javascript",
            "application/xml",
        ]

        if any(ct in content_type for ct in compressible_types):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Only compress if body is large enough (benefit from compression)
            if len(body) > 1024:  # 1KB threshold
                compressed = gzip.compress(body, compresslevel=6)
                response = Response(
                    content=compressed,
                    status_code=response.status_code,
                    headers={
                        **response.headers,
                        "Content-Encoding": "gzip",
                        "Content-Length": str(len(compressed)),
                    },
                    media_type=response.media_type,
                )
            else:
                response = Response(
                    content=body,
                    status_code=response.status_code,
                    headers=response.headers,
                    media_type=response.media_type,
                )

    return response
