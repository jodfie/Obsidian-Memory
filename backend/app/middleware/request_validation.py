"""Request validation middleware for API security.

Implements request size limits, Content-Type validation,
and path traversal protection.
"""

import re
from typing import Any

from fastapi import Request, Response
from starlette.responses import JSONResponse

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Path traversal patterns to detect
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",  # ../
    r"\.\.\\",  # ..\
    r"%2e%2e/",  # URL-encoded ../
    r"%2e%2e%2f",  # Fully URL-encoded ../
    r"%2e%2e\\",  # URL-encoded ..\
    r"\.\.%2f",  # Mixed encoding
    r"\.\.%5c",  # Mixed encoding
    r"%252e%252e",  # Double URL-encoded
]

# Compile patterns for efficiency
_TRAVERSAL_REGEX = re.compile(
    "|".join(PATH_TRAVERSAL_PATTERNS),
    re.IGNORECASE,
)


def _check_path_traversal(value: str) -> bool:
    """Check if a string contains path traversal attempts.

    Args:
        value: String to check

    Returns:
        True if path traversal detected, False otherwise
    """
    return bool(_TRAVERSAL_REGEX.search(value))


def _check_request_for_traversal(request: Request) -> str | None:
    """Check request path and query parameters for traversal attacks.

    Args:
        request: The incoming request

    Returns:
        The problematic parameter name if found, None otherwise
    """
    # Check URL path
    if _check_path_traversal(request.url.path):
        return "path"

    # Check query parameters
    for key, value in request.query_params.items():
        if _check_path_traversal(key) or _check_path_traversal(value):
            return f"query parameter '{key}'"

    return None


def _is_valid_content_type(request: Request) -> bool:
    """Check if Content-Type is valid for the request method.

    Args:
        request: The incoming request

    Returns:
        True if Content-Type is valid, False otherwise
    """
    # Only check POST, PUT, PATCH methods
    if request.method not in ["POST", "PUT", "PATCH"]:
        return True

    content_type = request.headers.get("Content-Type", "")

    # Allow JSON and form data
    valid_types = [
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",  # Some tools send this
    ]

    # Check if content type starts with any valid type
    # (handles charset and boundary parameters)
    return any(content_type.startswith(vt) for vt in valid_types) or not content_type


async def request_validation_middleware(
    request: Request,
    call_next: Any,
) -> Response:
    """Request validation middleware.

    Validates:
    - Request body size limits
    - Content-Type headers for POST/PUT/PATCH
    - Path traversal attempts in URL and query parameters

    Returns appropriate error responses for validation failures.
    """
    # Skip validation for health/metrics endpoints
    if request.url.path in ["/health", "/metrics", "/"]:
        return await call_next(request)

    # Check for path traversal attacks
    traversal_param = _check_request_for_traversal(request)
    if traversal_param:
        logger.warning(
            f"Path traversal attempt detected in {traversal_param} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        return JSONResponse(
            status_code=400,
            content={
                "detail": f"Invalid characters in {traversal_param}",
                "error": "path_traversal_detected",
            },
        )

    # Check Content-Type for mutating requests
    if not _is_valid_content_type(request):
        content_type = request.headers.get("Content-Type", "none")
        logger.warning(
            f"Invalid Content-Type '{content_type}' for {request.method} request"
        )
        return JSONResponse(
            status_code=415,
            content={
                "detail": f"Unsupported Content-Type: {content_type}",
                "error": "unsupported_media_type",
                "supported_types": [
                    "application/json",
                    "application/x-www-form-urlencoded",
                    "multipart/form-data",
                ],
            },
        )

    # Check request body size
    # Note: This checks Content-Length header; actual body size is validated
    # by FastAPI/Starlette during parsing
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            size = int(content_length)
            max_size = settings.max_request_size_bytes
            if size > max_size:
                logger.warning(
                    f"Request body too large: {size} bytes "
                    f"(max: {max_size} bytes)"
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body too large. Maximum size: {max_size} bytes",
                        "error": "request_entity_too_large",
                        "max_size_bytes": max_size,
                        "received_size_bytes": size,
                    },
                )
        except ValueError:
            # Invalid Content-Length header
            pass

    # Process request
    return await call_next(request)
