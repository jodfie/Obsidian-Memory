"""Tests for MCP proxy endpoints."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from app.api.mcp import router


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestMCPHealthProxy:
    """Tests for MCP health proxy endpoint."""

    def test_mcp_health_proxy_success(self, client):
        """Test successful health proxy."""
        mock_response = MagicMock()
        mock_response.content = b'{"status":"healthy"}'
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.get("/mcp/health")
            assert response.status_code == 200
            assert "status" in response.text

    def test_mcp_health_proxy_server_down(self, client):
        """Test health proxy when MCP server is down."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.get("/mcp/health")
            assert response.status_code == 503
            assert "unavailable" in response.text.lower()


class TestMCPStreamableHTTPProxy:
    """Tests for MCP Streamable HTTP proxy endpoint."""

    def test_mcp_streamable_http_post_success(self, client):
        """Test successful POST to MCP endpoint."""
        mock_response = MagicMock()
        mock_response.content = b'{"jsonrpc":"2.0","id":1,"result":{}}'
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json", "mcp-session-id": "test-session"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            )
            assert response.status_code == 200
            assert "mcp-session-id" in response.headers

    def test_mcp_streamable_http_post_server_unavailable(self, client):
        """Test POST when MCP server is unavailable."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
            )
            assert response.status_code == 503

    def test_mcp_session_id_forwarded_in_request(self, client):
        """Test that Mcp-Session-Id is forwarded from request."""
        mock_response = MagicMock()
        mock_response.content = b'{"jsonrpc":"2.0","id":1,"result":{}}'
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
                headers={"Mcp-Session-Id": "existing-session"},
            )
            assert response.status_code == 200


class TestMCPMessageProxy:
    """Tests for MCP message proxy endpoint."""

    def test_mcp_message_proxy_success(self, client):
        """Test successful message proxy."""
        mock_response = MagicMock()
        mock_response.content = b'{"jsonrpc":"2.0","id":1,"result":{}}'
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.post(
                "/mcp/message",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            )
            assert response.status_code == 200

    def test_mcp_message_proxy_timeout(self, client):
        """Test message proxy timeout."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=httpx.RequestError("Timeout"))
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.post(
                "/mcp/message",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            )
            assert response.status_code == 503


class TestMCPCORSOptions:
    """Tests for MCP CORS preflight handling."""

    def test_mcp_cors_options(self, client):
        """Test CORS OPTIONS request."""
        response = client.options("/mcp")
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

    def test_mcp_cors_options_with_path(self, client):
        """Test CORS OPTIONS request with path."""
        response = client.options("/mcp/health")
        assert response.status_code == 200
        assert "*" in response.headers.get("access-control-allow-origin", "")

    def test_mcp_cors_headers_include_session_id(self, client):
        """Test CORS allows Mcp-Session-Id header."""
        response = client.options("/mcp")
        allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
        assert "mcp-session-id" in allowed_headers


class TestMCPDeleteProxy:
    """Tests for MCP DELETE proxy endpoint."""

    def test_mcp_delete_proxy_success(self, client):
        """Test successful DELETE for session termination."""
        mock_response = MagicMock()
        mock_response.content = b''
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.delete = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.delete(
                "/mcp",
                headers={"Mcp-Session-Id": "test-session"},
            )
            assert response.status_code == 204

    def test_mcp_delete_proxy_server_unavailable(self, client):
        """Test DELETE when MCP server is unavailable."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.delete = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = client.delete("/mcp")
            assert response.status_code == 503
