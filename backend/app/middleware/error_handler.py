"""Error handling middleware."""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.exceptions import (
    AIProcessorError,
    AIProcessorUnavailableError,
    GitNotAvailableError,
    ParseError,
    SyncConflictError,
    SyncError,
    VaultError,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def error_handler_middleware(request: Request, call_next) -> JSONResponse:
    """Handle exceptions and return appropriate error responses.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        JSON error response
    """
    try:
        return await call_next(request)
    except VaultError as e:
        logger.warning(f"Vault error: {e}", extra={"extra_fields": {"error_type": "VaultError"}})
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(e), "error_type": "VaultError"},
        )
    except ParseError as e:
        logger.warning(f"Parse error: {e}", extra={"extra_fields": {"error_type": "ParseError"}})
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e), "error_type": "ParseError", "line_number": getattr(e, "line_number", None)},
        )
    except SyncConflictError as e:
        logger.warning(f"Sync conflict: {e}", extra={"extra_fields": {"error_type": "SyncConflictError"}})
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(e), "error_type": "SyncConflictError"},
        )
    except SyncError as e:
        logger.error(f"Sync error: {e}", extra={"extra_fields": {"error_type": "SyncError"}})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(e), "error_type": "SyncError"},
        )
    except GitNotAvailableError as e:
        logger.warning(f"Git not available: {e}", extra={"extra_fields": {"error_type": "GitNotAvailableError"}})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(e), "error_type": "GitNotAvailableError"},
        )
    except AIProcessorUnavailableError as e:
        logger.warning(f"AI processor unavailable: {e}", extra={"extra_fields": {"error_type": "AIProcessorUnavailableError"}})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(e), "error_type": "AIProcessorUnavailableError"},
        )
    except AIProcessorError as e:
        logger.error(f"AI processor error: {e}", extra={"extra_fields": {"error_type": "AIProcessorError"}})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(e), "error_type": "AIProcessorError"},
        )
    except Exception as e:
        logger.error(
            f"Unhandled exception: {e}",
            extra={"extra_fields": {"error_type": type(e).__name__}},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "error_type": "InternalError"},
        )
