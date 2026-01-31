"""Tests for request validation middleware."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.request_validation import (
    _check_path_traversal,
    _check_request_for_traversal,
    _is_valid_content_type,
    request_validation_middleware,
)


@pytest.fixture
def app():
    """Create a test FastAPI app with request validation middleware."""
    test_app = FastAPI()
    test_app.add_middleware(BaseHTTPMiddleware, dispatch=request_validation_middleware)

    @test_app.get("/test")
    async def test_get():
        return {"status": "ok"}

    @test_app.post("/test")
    async def test_post(data: dict = None):
        return {"received": data}

    @test_app.get("/files/{path:path}")
    async def get_file(path: str):
        return {"path": path}

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestPathTraversalDetection:
    """Tests for path traversal detection."""

    def test_detects_basic_traversal(self):
        """Should detect basic ../ traversal."""
        assert _check_path_traversal("../etc/passwd") is True
        assert _check_path_traversal("..\\windows\\system32") is True

    def test_detects_url_encoded_traversal(self):
        """Should detect URL-encoded traversal."""
        assert _check_path_traversal("%2e%2e/etc/passwd") is True
        assert _check_path_traversal("%2e%2e%2fetc%2fpasswd") is True

    def test_detects_mixed_encoding(self):
        """Should detect mixed encoding traversal."""
        assert _check_path_traversal("..%2fetc/passwd") is True
        assert _check_path_traversal("..%5cwindows") is True

    def test_detects_double_encoded(self):
        """Should detect double URL-encoded traversal."""
        assert _check_path_traversal("%252e%252e/etc") is True

    def test_allows_safe_paths(self):
        """Should allow safe paths."""
        assert _check_path_traversal("normal/path/file.txt") is False
        assert _check_path_traversal("projects/my-project/notes") is False
        assert _check_path_traversal("file.md") is False

    def test_allows_dots_in_filenames(self):
        """Should allow dots in filenames."""
        assert _check_path_traversal("file.name.txt") is False
        assert _check_path_traversal(".hidden") is False


class TestContentTypeValidation:
    """Tests for Content-Type validation."""

    def test_accepts_json_for_post(self):
        """Should accept application/json for POST."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"Content-Type": "application/json"}
        assert _is_valid_content_type(request) is True

    def test_accepts_json_with_charset(self):
        """Should accept application/json with charset."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"Content-Type": "application/json; charset=utf-8"}
        assert _is_valid_content_type(request) is True

    def test_accepts_form_data(self):
        """Should accept form data."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"Content-Type": "application/x-www-form-urlencoded"}
        assert _is_valid_content_type(request) is True

    def test_accepts_multipart(self):
        """Should accept multipart form data."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"Content-Type": "multipart/form-data; boundary=---"}
        assert _is_valid_content_type(request) is True

    def test_accepts_no_content_type_for_post(self):
        """Should accept missing Content-Type."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {}
        assert _is_valid_content_type(request) is True

    def test_skips_validation_for_get(self):
        """Should skip validation for GET requests."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.headers = {"Content-Type": "text/html"}
        assert _is_valid_content_type(request) is True

    def test_rejects_invalid_content_type(self):
        """Should reject invalid Content-Type for POST."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"Content-Type": "text/html"}
        assert _is_valid_content_type(request) is False


class TestRequestValidationMiddleware:
    """Integration tests for request validation middleware."""

    def test_allows_normal_requests(self, client):
        """Should allow normal requests."""
        response = client.get("/test")
        assert response.status_code == 200

    def test_blocks_path_traversal_in_url(self, client):
        """Should block path traversal in URL."""
        response = client.get("/files/../etc/passwd")
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "path_traversal_detected"

    def test_blocks_path_traversal_in_query(self, client):
        """Should block path traversal in query parameters."""
        response = client.get("/test?file=../etc/passwd")
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "path_traversal_detected"

    def test_allows_json_content_type(self, client):
        """Should allow JSON content type for POST."""
        response = client.post(
            "/test",
            json={"key": "value"},
        )
        assert response.status_code == 200

    def test_rejects_invalid_content_type(self, client):
        """Should reject invalid content type for POST."""
        response = client.post(
            "/test",
            content="<html></html>",
            headers={"Content-Type": "text/html"},
        )
        assert response.status_code == 415
        data = response.json()
        assert data["error"] == "unsupported_media_type"

    def test_skips_health_endpoint(self, client):
        """Should skip validation for health endpoint."""
        # Even with suspicious query params, health should work
        response = client.get("/health")
        assert response.status_code == 200

    @patch("app.middleware.request_validation.settings")
    def test_rejects_large_request(self, mock_settings, client):
        """Should reject requests exceeding size limit."""
        mock_settings.max_request_size_bytes = 100

        # Create a large payload
        large_data = {"data": "x" * 200}

        response = client.post(
            "/test",
            json=large_data,
        )
        assert response.status_code == 413
        data = response.json()
        assert data["error"] == "request_entity_too_large"


class TestCheckRequestForTraversal:
    """Tests for request traversal checking."""

    def test_detects_traversal_in_path(self):
        """Should detect traversal in URL path."""
        request = MagicMock(spec=Request)
        request.url.path = "/files/../etc/passwd"
        request.query_params = {}

        result = _check_request_for_traversal(request)
        assert result == "path"

    def test_detects_traversal_in_query_value(self):
        """Should detect traversal in query parameter value."""
        request = MagicMock(spec=Request)
        request.url.path = "/test"
        request.query_params = {"file": "../etc/passwd"}

        result = _check_request_for_traversal(request)
        assert result == "query parameter 'file'"

    def test_detects_traversal_in_query_key(self):
        """Should detect traversal in query parameter key."""
        request = MagicMock(spec=Request)
        request.url.path = "/test"
        request.query_params = {"../etc": "value"}

        result = _check_request_for_traversal(request)
        assert result == "query parameter '../etc'"

    def test_returns_none_for_safe_request(self):
        """Should return None for safe requests."""
        request = MagicMock(spec=Request)
        request.url.path = "/files/documents/report.pdf"
        request.query_params = {"format": "json", "limit": "10"}

        result = _check_request_for_traversal(request)
        assert result is None
