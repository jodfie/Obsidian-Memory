"""Tests for profile API endpoints."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app


def _mock_search_results(items: list | None = None):
    """Create a mock SearchResults object with .results and .total_count."""
    results = MagicMock()
    results.results = items or []
    results.total_count = len(results.results)
    return results


@pytest.fixture
def mock_search_index():
    """Mock search index for API tests."""
    index = AsyncMock()
    index.db = True  # Simulates initialized
    index.db_path = "/tmp/test.db"
    index.search = AsyncMock(return_value=_mock_search_results())
    index.index_note = AsyncMock()
    return index


@pytest.fixture
def mock_ai_processor():
    """Mock AI processor."""
    from app.models.note import ProfileNote
    processor = MagicMock()
    processor.synthesize_profile = AsyncMock(return_value=ProfileNote(
        project="test-proj",
        static_facts=["Uses Python", "Prefers FastAPI"],
        dynamic_patterns=["Focused on testing"],
        key_entities={"tools": ["pytest", "Docker"]},
        profile_version=1,
        synthesis_note_count=25,
    ))
    return processor


@pytest.fixture
async def client(mock_search_index, mock_ai_processor):
    """Create async test client with mocked dependencies."""
    from app.api.dependencies import get_search_index, get_ai_processor

    app.dependency_overrides[get_search_index] = lambda: mock_search_index
    app.dependency_overrides[get_ai_processor] = lambda: mock_ai_processor

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c

    app.dependency_overrides.clear()


class TestGetProfile:
    """Test GET /api/profile/{project}."""

    @pytest.mark.asyncio
    async def test_404_when_no_profile(self, client, mock_search_index):
        """Returns 404 when no profile note exists."""
        mock_search_index.search = AsyncMock(return_value=_mock_search_results())

        response = await client.get("/api/profile/my-project")

        assert response.status_code == 404
        assert "not synthesized yet" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_profile(self, client, mock_search_index):
        """Returns profile data when profile note exists."""
        profile_data = {
            "static_facts": ["Uses Python"],
            "dynamic_patterns": ["Writing tests"],
            "key_entities": {"tools": ["pytest"]},
            "profile_version": 2,
            "synthesis_note_count": 50,
        }

        mock_result = MagicMock()
        mock_result.content = json.dumps(profile_data)
        mock_result.updated_at = "2026-02-17T12:00:00"
        mock_search_index.search = AsyncMock(return_value=_mock_search_results([mock_result]))

        response = await client.get("/api/profile/my-project")

        assert response.status_code == 200
        data = response.json()
        assert data["project"] == "my-project"
        assert data["static_facts"] == ["Uses Python"]
        assert data["dynamic_patterns"] == ["Writing tests"]
        assert data["key_entities"]["tools"] == ["pytest"]
        assert data["profile_version"] == 2

    @pytest.mark.asyncio
    async def test_handles_invalid_json_content(self, client, mock_search_index):
        """Gracefully handles profile note with invalid JSON content."""
        mock_result = MagicMock()
        mock_result.content = "not json"
        mock_result.updated_at = "2026-02-17"
        mock_search_index.search = AsyncMock(return_value=_mock_search_results([mock_result]))

        response = await client.get("/api/profile/proj")

        assert response.status_code == 200
        data = response.json()
        assert data["static_facts"] == []
        assert data["project"] == "proj"


class TestSynthesizeProfile:
    """Test POST /api/profile/{project}/synthesize."""

    @pytest.mark.asyncio
    async def test_returns_202_accepted(self, client):
        """Synthesis trigger returns 202 Accepted."""
        response = await client.post("/api/profile/my-project/synthesize")

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["project"] == "my-project"
        assert "synthesis started" in data["message"]

    @pytest.mark.asyncio
    async def test_different_projects(self, client):
        """Can trigger synthesis for different projects."""
        r1 = await client.post("/api/profile/proj-a/synthesize")
        r2 = await client.post("/api/profile/proj-b/synthesize")

        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["project"] == "proj-a"
        assert r2.json()["project"] == "proj-b"
