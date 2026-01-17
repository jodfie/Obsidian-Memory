"""Tests for session management API endpoints."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.session_manager import SessionManager


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Create temporary storage directory."""
    storage = tmp_path / "sessions"
    storage.mkdir(parents=True)
    return storage


@pytest.fixture
def session_manager(temp_storage: Path) -> SessionManager:
    """Create session manager with temp storage."""
    return SessionManager(storage_path=temp_storage)


@pytest.fixture
async def client(session_manager: SessionManager):
    """Create test client with mocked session manager."""
    from app.api import sessions

    # Override the dependency
    app.dependency_overrides[sessions.get_session_manager] = lambda: session_manager

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    # Clean up
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient):
    """Test creating a new session."""
    response = await client.post("/api/sessions", json={"project": None})
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_observe_event(client: AsyncClient, session_manager: SessionManager):
    """Test observing an event in a session."""
    # Create a session first
    session = await session_manager.create_session()

    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": session.session_id,
            "event_type": "observation",
            "content": "Test observation",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session.session_id
    assert data["event_count"] == 1


@pytest.mark.asyncio
async def test_get_session(client: AsyncClient, session_manager: SessionManager):
    """Test getting a session by ID."""
    session = await session_manager.create_session(project="test-project")

    response = await client.get(f"/api/sessions/{session.session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session.session_id
    assert data["project"] == "test-project"


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient):
    """Test getting a non-existent session."""
    response = await client.get("/api/sessions/nonexistent-session")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_end_session(client: AsyncClient, session_manager: SessionManager):
    """Test ending a session."""
    session = await session_manager.create_session()

    response = await client.post(f"/api/sessions/{session.session_id}/end")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["ended_at"] is not None


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, session_manager: SessionManager):
    """Test listing sessions."""
    await session_manager.create_session(project="test-project")
    await session_manager.create_session(project="test-project")

    response = await client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) >= 2


@pytest.mark.asyncio
async def test_get_session_context(
    client: AsyncClient, session_manager: SessionManager
):
    """Test getting session context."""
    from app.models.session import SessionEventType

    session = await session_manager.create_session()
    await session_manager.observe_event(
        session.session_id, SessionEventType.OBSERVATION, "Test event"
    )

    response = await client.post(
        "/api/sessions/context",
        json={
            "session_id": session.session_id,
            "include_events": True,
            "include_summary": False,
            "limit": 50,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session.session_id
    assert "events" in data
    assert len(data["events"]) >= 1
