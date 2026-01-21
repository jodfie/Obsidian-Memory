"""Tests for Cloudflare Access middleware."""

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.cloudflare_access import cloudflare_access_middleware


def create_test_jwt(payload: dict, kid: str = "test-key-id") -> str:
    """Create a test JWT token (not cryptographically signed)."""
    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    header_b64 = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip('=')
    signature = "test_signature"
    signature_b64 = base64.urlsafe_b64encode(
        signature.encode()
    ).decode().rstrip('=')
    return f"{header_b64}.{payload_b64}.{signature_b64}"


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

    return app


def test_health_check_no_auth_required(app_with_cloudflare, monkeypatch):
    """Test that health check doesn't require Cloudflare Access."""
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
    from app.config import settings
    settings.cloudflare_access_enabled = True

    client = TestClient(app_with_cloudflare)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_protected_endpoint_no_token_when_disabled(app_with_cloudflare, monkeypatch):
    """Test that protected endpoints work when Cloudflare Access is disabled."""
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "false")
    from app.config import settings
    settings.cloudflare_access_enabled = False

    client = TestClient(app_with_cloudflare)
    response = client.get("/protected")
    assert response.status_code == 200
    assert response.json()["message"] == "protected"


def test_protected_endpoint_with_valid_token(app_with_cloudflare, monkeypatch):
    """Test that protected endpoints work with valid Cloudflare Access token."""
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
    from app.config import settings
    settings.cloudflare_access_enabled = True

    # Mock verify_cloudflare_access to return a valid identity
    with patch(
        "app.middleware.cloudflare_access.verify_cloudflare_access",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "aud": "test-audience", "iss": "https://test.cloudflareaccess.com"},
    ):
        payload = {
            "email": "user@example.com",
            "aud": "test-audience",
            "iss": "https://test.cloudflareaccess.com",
        }
        jwt_token = create_test_jwt(payload)

        client = TestClient(app_with_cloudflare)
        response = client.get(
            "/protected", headers={"CF-Access-JWT": jwt_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "protected"
        assert data["identity"]["email"] == "user@example.com"


def test_protected_endpoint_without_token_when_required(app_with_cloudflare, monkeypatch):
    """Test that protected endpoints require token when Cloudflare Access is enabled."""
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
    from app.config import settings
    settings.cloudflare_access_enabled = True

    client = TestClient(app_with_cloudflare)
    response = client.get("/protected")
    assert response.status_code == 401
    assert "Cloudflare Access JWT token required" in response.json()["detail"]


def test_protected_endpoint_with_invalid_token(app_with_cloudflare, monkeypatch):
    """Test that protected endpoints reject invalid tokens."""
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ENABLED", "true")
    from app.config import settings
    settings.cloudflare_access_enabled = True
    settings.cloudflare_access_team_domain = "test.cloudflareaccess.com"

    client = TestClient(app_with_cloudflare)
    response = client.get(
        "/protected", headers={"CF-Access-JWT": "invalid.token.here"}
    )
    assert response.status_code == 403
    assert "Invalid JWT format" in response.json()["detail"]
