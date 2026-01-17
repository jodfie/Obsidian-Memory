"""Logging middleware for request/response tracking."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging import get_logger

logger = get_logger(__name__)


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """Log HTTP requests and responses.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response from next handler
    """
    start_time = time.time()

    # Log request
    logger.info(
        "Request started",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": str(request.url.path),
                "query_params": str(request.query_params),
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            }
        },
    )

    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time

        # Log response
        logger.info(
            "Request completed",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "process_time": round(process_time, 4),
                }
            },
        )

        # Add process time header
        response.headers["X-Process-Time"] = str(round(process_time, 4))

        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            "Request failed",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "process_time": round(process_time, 4),
                }
            },
            exc_info=True,
        )
        raise
