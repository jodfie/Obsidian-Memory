"""Simple in-memory cache for frequently accessed data."""

import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class SimpleCache:
    """Simple TTL-based cache."""

    def __init__(self, default_ttl: int = 300) -> None:
        """Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Delete key from cache.

        Args:
            key: Cache key
        """
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items() if now > expiry
        ]
        for key in expired_keys:
            del self._cache[key]


# Global cache instance
_cache = SimpleCache(default_ttl=300)


def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator for caching function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"

            # Check cache
            cached_value = _cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            _cache.set(cache_key, result, ttl=ttl)
            return result

        return wrapper
    return decorator


def get_cache() -> SimpleCache:
    """Get global cache instance.

    Returns:
        Cache instance
    """
    return _cache
