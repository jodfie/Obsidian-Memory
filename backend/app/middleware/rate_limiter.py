"""Rate limiting middleware for API protection.

Implements a sliding window rate limiter with configurable limits per IP address.
Uses an in-memory store suitable for single-instance deployments.
For multi-instance deployments, extend to use Redis.
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Any

from fastapi import Request, Response
from starlette.responses import JSONResponse

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# In-memory rate limit store
# Structure: {ip_address: [(timestamp, count), ...]}
_rate_limit_store: dict[str, list[tuple[float, int]]] = defaultdict(list)
_store_lock = Lock()

# Cleanup interval (remove old entries every N requests)
_cleanup_counter = 0
_CLEANUP_INTERVAL = 100


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies."""
    # Check for forwarded headers (from reverse proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (original client)
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct connection IP
    if request.client:
        return request.client.host

    return "unknown"


def _cleanup_old_entries(window_seconds: int = 60) -> None:
    """Remove expired entries from the rate limit store."""
    global _cleanup_counter
    _cleanup_counter += 1

    if _cleanup_counter < _CLEANUP_INTERVAL:
        return

    _cleanup_counter = 0
    cutoff = time.time() - window_seconds

    with _store_lock:
        for ip in list(_rate_limit_store.keys()):
            # Keep only recent entries
            _rate_limit_store[ip] = [
                (ts, count) for ts, count in _rate_limit_store[ip] if ts > cutoff
            ]
            # Remove empty entries
            if not _rate_limit_store[ip]:
                del _rate_limit_store[ip]


def _check_rate_limit(
    client_ip: str,
    max_requests: int,
    burst: int,
    window_seconds: int = 60,
) -> tuple[bool, int, int]:
    """Check if request is within rate limit.

    Args:
        client_ip: Client IP address
        max_requests: Maximum requests per window
        burst: Additional burst allowance
        window_seconds: Time window in seconds

    Returns:
        Tuple of (is_allowed, remaining_requests, retry_after_seconds)
    """
    now = time.time()
    cutoff = now - window_seconds
    effective_limit = max_requests + burst

    with _store_lock:
        # Get entries within the window
        entries = _rate_limit_store[client_ip]
        recent_entries = [(ts, count) for ts, count in entries if ts > cutoff]

        # Count total requests in window
        total_requests = sum(count for _, count in recent_entries)

        if total_requests >= effective_limit:
            # Calculate retry-after based on oldest entry
            if recent_entries:
                oldest_ts = min(ts for ts, _ in recent_entries)
                retry_after = int(oldest_ts + window_seconds - now) + 1
            else:
                retry_after = window_seconds
            return False, 0, max(1, retry_after)

        # Add new request
        recent_entries.append((now, 1))
        _rate_limit_store[client_ip] = recent_entries

        remaining = effective_limit - total_requests - 1
        return True, max(0, remaining), 0


def _add_rate_limit_headers(
    response: Response,
    limit: int,
    remaining: int,
    reset_seconds: int = 60,
) -> None:
    """Add rate limit headers to response."""
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + reset_seconds)


async def rate_limit_middleware(
    request: Request,
    call_next: Any,
) -> Response:
    """Rate limiting middleware.

    Implements sliding window rate limiting per IP address.
    Adds rate limit headers to all responses.
    Returns 429 Too Many Requests when limit is exceeded.
    """
    # Skip rate limiting if disabled
    if not settings.rate_limit_enabled:
        return await call_next(request)

    # Skip rate limiting for health/metrics endpoints
    if request.url.path in ["/health", "/metrics", "/"]:
        return await call_next(request)

    # Trigger cleanup periodically
    _cleanup_old_entries()

    client_ip = _get_client_ip(request)
    max_requests = settings.rate_limit_requests_per_minute
    burst = settings.rate_limit_burst

    is_allowed, remaining, retry_after = _check_rate_limit(
        client_ip, max_requests, burst
    )

    if not is_allowed:
        logger.warning(
            f"Rate limit exceeded for IP {client_ip}, "
            f"retry after {retry_after}s"
        )
        response = JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please try again later.",
                "retry_after": retry_after,
            },
        )
        _add_rate_limit_headers(response, max_requests + burst, 0)
        response.headers["Retry-After"] = str(retry_after)
        return response

    # Process request
    response = await call_next(request)

    # Add rate limit headers to successful responses
    _add_rate_limit_headers(response, max_requests + burst, remaining)

    return response


def reset_rate_limits() -> None:
    """Reset all rate limits. Useful for testing."""
    global _cleanup_counter
    with _store_lock:
        _rate_limit_store.clear()
    _cleanup_counter = 0
