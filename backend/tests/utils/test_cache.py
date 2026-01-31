"""Tests for cache utility."""

import time
import pytest

from app.utils.cache import SimpleCache, cached, get_cache


class TestSimpleCache:
    """Tests for SimpleCache class."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = SimpleCache(default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """Test getting a key that doesn't exist."""
        cache = SimpleCache()
        assert cache.get("nonexistent") is None

    def test_get_expired(self):
        """Test getting an expired key."""
        cache = SimpleCache(default_ttl=0)  # Immediate expiry
        cache.set("key1", "value1", ttl=0)
        time.sleep(0.1)  # Wait for expiry
        assert cache.get("key1") is None

    def test_set_custom_ttl(self):
        """Test setting with custom TTL."""
        cache = SimpleCache(default_ttl=60)
        cache.set("key1", "value1", ttl=3600)
        assert cache.get("key1") == "value1"

    def test_delete(self):
        """Test deleting a key."""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent(self):
        """Test deleting a key that doesn't exist."""
        cache = SimpleCache()
        cache.delete("nonexistent")  # Should not raise

    def test_clear(self):
        """Test clearing all entries."""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = SimpleCache()
        cache.set("keep", "value", ttl=3600)
        # Set expiry manually in the past
        cache._cache["expire"] = ("value", time.time() - 1)
        cache.cleanup_expired()
        assert cache.get("keep") == "value"
        assert "expire" not in cache._cache


class TestCachedDecorator:
    """Tests for @cached decorator."""

    def test_cached_function(self):
        """Test caching function results."""
        call_count = 0

        @cached(ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call with same args - should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not incremented

        # Different args - should call function
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    def test_cached_with_key_prefix(self):
        """Test caching with key prefix."""
        @cached(ttl=60, key_prefix="test")
        def my_function(x):
            return x + 1

        result = my_function(1)
        assert result == 2


class TestGetCache:
    """Tests for get_cache function."""

    def test_get_cache_returns_instance(self):
        """Test that get_cache returns a cache instance."""
        cache = get_cache()
        assert isinstance(cache, SimpleCache)

    def test_get_cache_singleton(self):
        """Test that get_cache returns the same instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2
