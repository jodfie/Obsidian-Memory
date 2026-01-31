"""Comprehensive tests for Cloudflare Access authentication middleware.

Tests both CF-Access-JWT (browser-based) and OAuth Bearer token flows,
JWKS caching, internal network bypass, and error handling.
"""

import base64
import ipaddress
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.cloudflare_access import (
    cloudflare_access_middleware,
    get_cloudflare_public_keys,
    is_trusted_internal_request,
    verify_cloudflare_access,
    CACHE_TTL,
    _public_keys_cache,
    _cache_expiry,
)


def generate_rsa_keypair():
    """Generate RSA key pair for testing JWT signatures."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # Convert to JWK format for JWKS
    public_numbers = public_key.public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "test-key-id",
        "n": base64.urlsafe_b64encode(
            public_numbers.n.to_bytes(256, 'big')
        ).decode().rstrip('='),
        "e": base64.urlsafe_b64encode(
            public_numbers.e.to_bytes(3, 'big')
        ).decode().rstrip('='),
    }

    return private_key, jwk


def create_signed_jwt(
    payload: Dict[str, Any],
    private_key,
    kid: str = "test-key-id"
) -> str:
    """Create a properly signed JWT token for testing."""
    headers = {"kid": kid}
    return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)


@pytest.fixture
def rsa_keys():
    """Generate RSA key pair for JWT signing."""
    return generate_rsa_keypair()


@pytest.fixture
def app_with_cloudflare():
    """Create FastAPI app with Cloudflare Access middleware."""
    app = FastAPI()
    app.add_middleware(BaseHTTPMiddleware, dispatch=cloudflare_access_middleware)

    @app.get("/protected")
    async def protected(request: Request):
        identity = getattr(request.state, 'cloudflare_identity', None)
        return {"message": "protected", "identity": identity}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.options("/protected")
    async def options_protected():
        return {"message": "CORS preflight"}

    @app.get("/mcp/authorize")
    async def mcp_authorize():
        return {"message": "OAuth authorize endpoint"}

    @app.post("/mcp/token")
    async def mcp_token():
        return {"message": "OAuth token endpoint"}

    return app


class TestInternalNetworkBypass:
    """Test internal network bypass functionality."""

    def test_internal_network_detection(self):
        """Test detection of internal network IPs."""
        # Create mock requests with different IPs
        mock_request = MagicMock(spec=Request)

        # Test Docker network IP
        mock_request.client.host = "172.17.0.2"
        assert is_trusted_internal_request(mock_request) is True

        # Test private network range A
        mock_request.client.host = "10.0.1.5"
        assert is_trusted_internal_request(mock_request) is True

        # Test private network range C
        mock_request.client.host = "192.168.1.100"
        assert is_trusted_internal_request(mock_request) is True

        # Test localhost
        mock_request.client.host = "127.0.0.1"
        assert is_trusted_internal_request(mock_request) is True

        # Test external IP (should not be trusted)
        mock_request.client.host = "8.8.8.8"
        assert is_trusted_internal_request(mock_request) is False

    def test_internal_bypass_disabled_flag(self, monkeypatch):
        """Test DISABLE_INTERNAL_BYPASS environment variable."""
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "172.17.0.2"

        # With bypass enabled (default)
        monkeypatch.setenv("DISABLE_INTERNAL_BYPASS", "false")
        from importlib import reload
        import app.middleware.cloudflare_access as cf_access
        reload(cf_access)
        assert cf_access.is_trusted_internal_request(mock_request) is True

        # With bypass disabled
        monkeypatch.setenv("DISABLE_INTERNAL_BYPASS", "true")
        reload(cf_access)
        assert cf_access.is_trusted_internal_request(mock_request) is False

    def test_invalid_ip_format_handling(self):
        """Test handling of invalid IP addresses."""
        mock_request = MagicMock(spec=Request)

        # Invalid IP format
        mock_request.client.host = "not-an-ip"
        assert is_trusted_internal_request(mock_request) is False

        # Empty host
        mock_request.client.host = ""
        assert is_trusted_internal_request(mock_request) is False

        # None client
        mock_request.client = None
        assert is_trusted_internal_request(mock_request) is False


class TestJWKSCaching:
    """Test JWKS caching functionality."""

    @pytest.mark.asyncio
    async def test_jwks_caching(self, rsa_keys):
        """Test that JWKS are cached and reused."""
        private_key, jwk = rsa_keys
        team_domain = "test.cloudflareaccess.com"

        # Clear cache
        _public_keys_cache.clear()
        _cache_expiry.clear()

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [jwk]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock()

            # First call should fetch from API
            keys1 = await get_cloudflare_public_keys(team_domain)
            assert jwk["kid"] in keys1
            assert mock_client.get.call_count == 1

            # Second call should use cache
            keys2 = await get_cloudflare_public_keys(team_domain)
            assert keys1 == keys2
            assert mock_client.get.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_jwks_cache_expiry(self, rsa_keys):
        """Test that JWKS cache expires after TTL."""
        private_key, jwk = rsa_keys
        team_domain = "test.cloudflareaccess.com"

        # Clear cache
        _public_keys_cache.clear()
        _cache_expiry.clear()

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.json.return_value = {"keys": [jwk]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock()

            # First call
            await get_cloudflare_public_keys(team_domain)
            assert mock_client.get.call_count == 1

            # Manually expire cache
            cache_key = f"jwks_{team_domain}"
            _cache_expiry[cache_key] = time.time() - 1  # Expired

            # Should fetch again
            await get_cloudflare_public_keys(team_domain)
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_jwks_fetch_error_handling(self):
        """Test error handling when JWKS fetch fails."""
        team_domain = "test.cloudflareaccess.com"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock()

            with pytest.raises(Exception) as exc_info:
                await get_cloudflare_public_keys(team_domain)
            assert "Failed to fetch Cloudflare Access public keys" in str(exc_info.value)


class TestJWTVerification:
    """Test JWT verification for both CF-Access-JWT and Bearer tokens."""

    @pytest.mark.asyncio
    async def test_cf_access_jwt_header(self, rsa_keys, monkeypatch):
        """Test CF-Access-JWT header authentication."""
        private_key, jwk = rsa_keys
        team_domain = "test.cloudflareaccess.com"

        # Configure settings
        monkeypatch.setattr("app.config.settings.cloudflare_access_enabled", True)
        monkeypatch.setattr("app.config.settings.cloudflare_access_team_domain", team_domain)

        # Create valid JWT
        payload = {
            "email": "user@example.com",
            "aud": team_domain,
            "iss": f"https://{team_domain}",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        jwt_token = create_signed_jwt(payload, private_key)

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"CF-Access-JWT": jwt_token}

        # Mock JWKS fetch
        with patch(
            "app.middleware.cloudflare_access.get_cloudflare_public_keys",
            new_callable=AsyncMock,
            return_value={jwk["kid"]: jwk}
        ):
            identity = await verify_cloudflare_access(mock_request)
            assert identity["email"] == "user@example.com"
            assert identity["aud"] == team_domain

    @pytest.mark.asyncio
    async def test_oauth_bearer_token(self, rsa_keys, monkeypatch):
        """Test OAuth Bearer token authentication."""
        private_key, jwk = rsa_keys
        team_domain = "test.cloudflareaccess.com"
        oauth_client_id = "test-oauth-client-id"

        # Configure settings
        monkeypatch.setattr("app.config.settings.cloudflare_access_enabled", True)
        monkeypatch.setattr("app.config.settings.cloudflare_access_team_domain", team_domain)
        monkeypatch.setattr("app.config.settings.cloudflare_oauth_client_id", oauth_client_id)

        # Create valid JWT with OAuth client_id as audience
        payload = {
            "sub": "oauth-user@example.com",
            "aud": oauth_client_id,
            "iss": f"https://{team_domain}",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        jwt_token = create_signed_jwt(payload, private_key)

        # Mock request with Bearer token
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": f"Bearer {jwt_token}"}

        # Mock JWKS fetch
        with patch(
            "app.middleware.cloudflare_access.get_cloudflare_public_keys",
            new_callable=AsyncMock,
            return_value={jwk["kid"]: jwk}
        ):
            identity = await verify_cloudflare_access(mock_request)
            assert identity["email"] == "oauth-user@example.com"
            assert identity["aud"] == oauth_client_id

    @pytest.mark.asyncio
    async def test_expired_token(self, rsa_keys, monkeypatch):
        """Test rejection of expired JWT tokens."""
        private_key, jwk = rsa_keys
        team_domain = "test.cloudflareaccess.com"

        # Configure settings
        monkeypatch.setattr("app.config.settings.cloudflare_access_enabled", True)
        monkeypatch.setattr("app.config.settings.cloudflare_access_team_domain", team_domain)

        # Create expired JWT
        payload = {
            "email": "user@example.com",
            "aud": team_domain,
            "iss": f"https://{team_domain}",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        jwt_token = create_signed_jwt(payload, private_key)

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"CF-Access-JWT": jwt_token}

        # Mock JWKS fetch
        with patch(
            "app.middleware.cloudflare_access.get_cloudflare_public_keys",
            new_callable=AsyncMock,
            return_value={jwk["kid"]: jwk}
        ):
            with pytest.raises(Exception) as exc_info:
                await verify_cloudflare_access(mock_request)
            assert "expired" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_kid_header(self, monkeypatch):
        """Test rejection of JWT without kid header."""
        team_domain = "test.cloudflareaccess.com"

        # Configure settings
        monkeypatch.setattr("app.config.settings.cloudflare_access_enabled", True)
        monkeypatch.setattr("app.config.settings.cloudflare_access_team_domain", team_domain)

        # Create JWT without kid header
        payload = {"email": "user@example.com"}
        jwt_token = jwt.encode(payload, "secret", algorithm="HS256")

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"CF-Access-JWT": jwt_token}

        with pytest.raises(Exception) as exc_info:
            await verify_cloudflare_access(mock_request)
        assert "Invalid JWT format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_jwt_format(self, monkeypatch):
        """Test rejection of malformed JWT."""
        team_domain = "test.cloudflareaccess.com"

        # Configure settings
        monkeypatch.setattr("app.config.settings.cloudflare_access_enabled", True)
        monkeypatch.setattr("app.config.settings.cloudflare_access_team_domain", team_domain)

        # Mock request with invalid JWT
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"CF-Access-JWT": "not.a.valid.jwt"}

        with pytest.raises(Exception) as exc_info:
            await verify_cloudflare_access(mock_request)
        assert "Invalid JWT format" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_token(self, monkeypatch):
        """Test error when no token is provided."""
        # Configure settings
        monkeypatch.setattr("app.config.settings.cloudflare_access_enabled", True)
        monkeypatch.setattr("app.config.settings.cloudflare_access_team_domain", "test.cloudflareaccess.com")

        # Mock request without token
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}

        with pytest.raises(Exception) as exc_info:
            await verify_cloudflare_access(mock_request)
        assert "JWT token required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_team_domain_config(self, monkeypatch):
        """Test error when team domain is not configured."""
        # Configure settings
        monkeypatch.setattr("app.config.settings.cloudflare_access_enabled", True)
        monkeypatch.setattr("app.config.settings.cloudflare_access_team_domain", None)

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"CF-Access-JWT": "some.jwt.token"}

        with pytest.raises(Exception) as exc_info:
            await verify_cloudflare_access(mock_request)
        assert "team domain not configured" in str(exc_info.value)


class TestMiddlewareIntegration:
    """Test full middleware integration with FastAPI."""

    def test_options_request_bypass(self, app_with_cloudflare, monkeypatch):
        """Test that OPTIONS requests bypass authentication."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
        from app.config import settings
        settings.cloudflare_access_enabled = True

        client = TestClient(app_with_cloudflare)
        response = client.options("/protected")
        assert response.status_code == 200

    def test_health_endpoint_bypass(self, app_with_cloudflare, monkeypatch):
        """Test that health check bypasses authentication."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
        from app.config import settings
        settings.cloudflare_access_enabled = True

        client = TestClient(app_with_cloudflare)
        response = client.get("/health")
        assert response.status_code == 200

    def test_oauth_endpoints_bypass(self, app_with_cloudflare, monkeypatch):
        """Test that OAuth endpoints bypass authentication."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
        from app.config import settings
        settings.cloudflare_access_enabled = True

        client = TestClient(app_with_cloudflare)

        # Test authorize endpoint
        response = client.get("/mcp/authorize")
        assert response.status_code == 200

        # Test token endpoint
        response = client.post("/mcp/token")
        assert response.status_code == 200

    def test_internal_network_bypass(self, app_with_cloudflare, monkeypatch):
        """Test that internal network requests bypass Cloudflare auth."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
        monkeypatch.setenv("DISABLE_INTERNAL_BYPASS", "false")
        from app.config import settings
        settings.cloudflare_access_enabled = True

        # Mock internal IP
        with patch(
            "app.middleware.cloudflare_access.is_trusted_internal_request",
            return_value=True
        ):
            client = TestClient(app_with_cloudflare)
            response = client.get("/protected")
            assert response.status_code == 200

    def test_auth_disabled_globally(self, app_with_cloudflare, monkeypatch):
        """Test that authentication can be disabled globally."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "false")
        from app.config import settings
        settings.cloudflare_access_enabled = False

        client = TestClient(app_with_cloudflare)
        response = client.get("/protected")
        assert response.status_code == 200

        # Verify no identity is attached
        data = response.json()
        assert data["identity"] is None


class TestErrorHandling:
    """Test comprehensive error handling scenarios."""

    def test_401_without_token(self, app_with_cloudflare, monkeypatch):
        """Test 401 response when token is missing."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
        from app.config import settings
        settings.cloudflare_access_enabled = True

        client = TestClient(app_with_cloudflare)
        response = client.get("/protected")
        assert response.status_code == 401
        assert "JWT token required" in response.json()["detail"]

    def test_403_with_invalid_token(self, app_with_cloudflare, monkeypatch):
        """Test 403 response when token is invalid."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
        from app.config import settings
        settings.cloudflare_access_enabled = True
        settings.cloudflare_access_team_domain = "test.cloudflareaccess.com"

        client = TestClient(app_with_cloudflare)
        response = client.get(
            "/protected",
            headers={"CF-Access-JWT": "invalid.jwt.token"}
        )
        assert response.status_code == 403
        assert "Invalid JWT format" in response.json()["detail"]

    def test_500_with_missing_config(self, app_with_cloudflare, monkeypatch):
        """Test 500 response when configuration is missing."""
        monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
        from app.config import settings
        settings.cloudflare_access_enabled = True
        settings.cloudflare_access_team_domain = None

        client = TestClient(app_with_cloudflare)
        response = client.get(
            "/protected",
            headers={"CF-Access-JWT": "some.jwt.token"}
        )
        assert response.status_code == 500
        assert "team domain not configured" in response.json()["detail"]