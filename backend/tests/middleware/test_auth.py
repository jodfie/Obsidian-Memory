"""Tests for authentication middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.auth import auth_middleware


@pytest.fixture
def app_with_auth():
    """Create FastAPI app with auth middleware."""
    app = FastAPI()
    app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

    @app.get("/protected")
    async def protected():
        return {"message": "protected"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


@pytest.fixture
def app_without_auth():
    """Create FastAPI app without auth middleware."""
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        return {"message": "protected"}

    return app


def test_health_check_no_auth_required(app_with_auth):
    """Test that health check doesn't require auth."""
    client = TestClient(app_with_auth)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_protected_endpoint_no_token_required_when_disabled(app_without_auth):
    """Test that protected endpoints work when auth is disabled."""
    client = TestClient(app_without_auth)
    response = client.get("/protected")
    assert response.status_code == 200
    assert response.json() == {"message": "protected"}


def test_protected_endpoint_with_valid_token(app_with_auth, monkeypatch):
    """Test that protected endpoints work with valid token."""
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("API_TOKEN", "test-token-123")

    # Reload settings
    from app.config import settings
    settings.require_auth = True
    settings.api_token = "test-token-123"

    client = TestClient(app_with_auth)
    response = client.get(
        "/protected", headers={"Authorization": "Bearer test-token-123"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "protected"}


def test_protected_endpoint_with_invalid_token(app_with_auth, monkeypatch):
    """Test that protected endpoints reject invalid tokens."""
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("API_TOKEN", "test-token-123")

    # Reload settings
    from app.config import settings
    settings.require_auth = True
    settings.api_token = "test-token-123"

    client = TestClient(app_with_auth)
    response = client.get(
        "/protected", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 403
    assert "Invalid authentication token" in response.json()["detail"]


def test_protected_endpoint_without_token_when_required(app_with_auth, monkeypatch):
    """Test that protected endpoints require token when auth is enabled."""
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("API_TOKEN", "test-token-123")

    # Reload settings
    from app.config import settings
    settings.require_auth = True
    settings.api_token = "test-token-123"

    client = TestClient(app_with_auth)
    response = client.get("/protected")
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]
