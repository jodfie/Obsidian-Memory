"""Tests for rate limiting middleware."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.rate_limiter import (
    _check_rate_limit,
    _get_client_ip,
    rate_limit_middleware,
    reset_rate_limits,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with rate limiting middleware."""
    test_app = FastAPI()
    test_app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

    @test_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @test_app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_limits():
    """Reset rate limits before each test."""
    reset_rate_limits()
    yield
    reset_rate_limits()


class TestGetClientIP:
    """Tests for client IP extraction."""

    def test_extracts_ip_from_x_forwarded_for(self):
        """Should extract first IP from X-Forwarded-For header."""
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1, 172.16.0.1"}
        request.client = MagicMock(host="127.0.0.1")

        ip = _get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_extracts_ip_from_x_real_ip(self):
        """Should extract IP from X-Real-IP header."""
        request = MagicMock(spec=Request)
        request.headers = {"X-Real-IP": "192.168.1.100"}
        request.client = MagicMock(host="127.0.0.1")

        ip = _get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_falls_back_to_client_host(self):
        """Should fall back to direct connection IP."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = MagicMock(host="10.0.0.50")

        ip = _get_client_ip(request)
        assert ip == "10.0.0.50"

    def test_returns_unknown_when_no_ip(self):
        """Should return 'unknown' when no IP available."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None

        ip = _get_client_ip(request)
        assert ip == "unknown"


class TestCheckRateLimit:
    """Tests for rate limit checking logic."""

    def test_allows_request_within_limit(self):
        """Should allow requests within the limit."""
        is_allowed, remaining, retry_after = _check_rate_limit(
            "192.168.1.1", max_requests=10, burst=5
        )
        assert is_allowed is True
        assert remaining == 14  # 10 + 5 - 1
        assert retry_after == 0

    def test_decrements_remaining_count(self):
        """Should decrement remaining count with each request."""
        for i in range(5):
            is_allowed, remaining, _ = _check_rate_limit(
                "192.168.1.2", max_requests=10, burst=0
            )
            assert is_allowed is True
            assert remaining == 10 - i - 1

    def test_blocks_when_limit_exceeded(self):
        """Should block requests when limit is exceeded."""
        # Exhaust the limit
        for _ in range(15):
            _check_rate_limit("192.168.1.3", max_requests=10, burst=5)

        # Next request should be blocked
        is_allowed, remaining, retry_after = _check_rate_limit(
            "192.168.1.3", max_requests=10, burst=5
        )
        assert is_allowed is False
        assert remaining == 0
        assert retry_after > 0

    def test_different_ips_have_separate_limits(self):
        """Should track limits separately for different IPs."""
        # Exhaust limit for IP 1
        for _ in range(15):
            _check_rate_limit("192.168.1.10", max_requests=10, burst=5)

        # IP 1 should be blocked
        is_allowed1, _, _ = _check_rate_limit(
            "192.168.1.10", max_requests=10, burst=5
        )
        assert is_allowed1 is False

        # IP 2 should still be allowed
        is_allowed2, _, _ = _check_rate_limit(
            "192.168.1.20", max_requests=10, burst=5
        )
        assert is_allowed2 is True


class TestRateLimitMiddleware:
    """Integration tests for rate limit middleware."""

    @patch("app.middleware.rate_limiter.settings")
    def test_adds_rate_limit_headers(self, mock_settings, client):
        """Should add rate limit headers to responses."""
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 60
        mock_settings.rate_limit_burst = 10

        response = client.get("/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @patch("app.middleware.rate_limiter.settings")
    def test_skips_health_endpoint(self, mock_settings, client):
        """Should skip rate limiting for health endpoint."""
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 1
        mock_settings.rate_limit_burst = 0

        # Make many requests to health endpoint
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200

    @patch("app.middleware.rate_limiter.settings")
    def test_returns_429_when_limit_exceeded(self, mock_settings, client):
        """Should return 429 when rate limit is exceeded."""
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 2
        mock_settings.rate_limit_burst = 1

        # Make requests up to the limit
        for _ in range(3):
            client.get("/test")

        # Next request should be rate limited
        response = client.get("/test")
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        data = response.json()
        assert "retry_after" in data
        assert data["detail"] == "Too many requests. Please try again later."

    @patch("app.middleware.rate_limiter.settings")
    def test_disabled_when_setting_is_false(self, mock_settings, client):
        """Should not rate limit when disabled."""
        mock_settings.rate_limit_enabled = False

        # Make many requests
        for _ in range(100):
            response = client.get("/test")
            assert response.status_code == 200
