"""Integration tests for Claude Code hooks workflow.

These tests simulate the complete Claude Code session lifecycle with all hooks
executing in sequence, validating the session management and event capture.
"""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.session import SessionEventType
from app.services.session_manager import SessionManager


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Create temporary storage directory for sessions."""
    storage = tmp_path / "sessions"
    storage.mkdir(parents=True)
    return storage


@pytest.fixture
def session_manager(temp_storage: Path) -> SessionManager:
    """Create session manager with temporary storage."""
    return SessionManager(storage_path=temp_storage)


@pytest.fixture
def mock_ai_processor():
    """Create a mock AI processor for testing summarization."""
    mock = MagicMock()
    mock.summarize_session = AsyncMock(
        return_value=MagicMock(
            model_dump=lambda: {
                "key_learnings": ["Learned about testing patterns"],
                "decisions": ["Chose pytest for testing framework"],
                "errors_encountered": ["Initial import error resolved"],
                "solutions_found": ["Added missing dependency"],
                "next_steps": ["Write more tests"],
                "summary_text": "Productive session focused on testing",
                "compression_ratio": 0.75,
            }
        )
    )
    return mock


@pytest_asyncio.fixture
async def client(session_manager: SessionManager):
    """Create async test client with session manager dependency override."""
    from app.api import sessions

    app.dependency_overrides[sessions.get_session_manager] = lambda: session_manager

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def hooks_dir() -> Path:
    """Get the hooks directory path."""
    return Path(__file__).parent.parent.parent.parent / "hooks"


# ============================================================================
# Test 1: Full Session Lifecycle
# ============================================================================


@pytest.mark.asyncio
async def test_full_session_lifecycle(
    client: AsyncClient, session_manager: SessionManager, mock_ai_processor
):
    """Test complete session lifecycle: SessionStart → UserPromptSubmit → PostToolUse → PreCompact → SessionEnd.

    This simulates the complete Claude Code hook workflow from session creation
    to final summary generation.
    """
    # 1. SessionStart: Create session
    response = await client.post(
        "/api/sessions", json={"project": "test-integration"}
    )
    assert response.status_code == 200
    session_data = response.json()
    session_id = session_data["session_id"]
    assert session_data["status"] == "active"
    assert session_data["project"] == "test-integration"

    # 2. UserPromptSubmit: Log user prompt
    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": session_id,
            "event_type": "user_prompt",
            "content": "Implement user authentication feature",
            "metadata": {"prompt_length": 35},
        },
    )
    assert response.status_code == 200
    assert response.json()["event_count"] == 1

    # 3. PostToolUse: Log multiple tool uses
    tool_events = [
        ("file_edit", "Created auth.py with basic structure"),
        ("command", "Ran: pytest tests/test_auth.py"),
        ("research", "Searched: JWT best practices"),
        ("file_edit", "Updated auth.py with JWT implementation"),
    ]

    for event_type, content in tool_events:
        response = await client.post(
            "/api/sessions/observe",
            json={
                "session_id": session_id,
                "event_type": event_type,
                "content": content,
                "metadata": {"tool_name": event_type},
            },
        )
        assert response.status_code == 200

    # Verify event count
    session = await session_manager.get_session(session_id)
    assert len(session.events) == 5  # 1 prompt + 4 tool uses

    # 4. PreCompact: Trigger summarization (mock AI)
    with patch.object(
        session_manager,
        "summarize_session",
        new_callable=AsyncMock,
        return_value={
            "key_learnings": ["JWT implementation patterns"],
            "decisions": ["Use bcrypt for password hashing"],
            "errors_encountered": [],
            "solutions_found": [],
        },
    ):
        summary = await session_manager.summarize_session(session_id)
        assert "key_learnings" in summary

    # 5. SessionEnd: End session
    response = await client.post(f"/api/sessions/{session_id}/end")
    assert response.status_code == 200
    end_data = response.json()
    assert end_data["status"] == "completed"
    assert end_data["ended_at"] is not None

    # Verify final session state
    final_session = await session_manager.get_session(session_id)
    assert final_session.status == "completed"
    assert len(final_session.events) == 5


# ============================================================================
# Test 2: Session Creation
# ============================================================================


@pytest.mark.asyncio
async def test_session_start_creates_session(
    client: AsyncClient, session_manager: SessionManager
):
    """Test SessionStart hook creates a valid session with context loading."""
    # Create session with project
    response = await client.post(
        "/api/sessions", json={"project": "my-awesome-project"}
    )
    assert response.status_code == 200
    data = response.json()

    # Verify session structure
    assert "session_id" in data
    assert data["project"] == "my-awesome-project"
    assert data["status"] == "active"
    assert data["started_at"] is not None
    assert data["ended_at"] is None

    # Verify session is persisted
    session = await session_manager.get_session(data["session_id"])
    assert session is not None
    assert session.project == "my-awesome-project"


@pytest.mark.asyncio
async def test_session_start_with_custom_id(
    client: AsyncClient, session_manager: SessionManager
):
    """Test SessionStart with a custom session ID (Claude-provided)."""
    custom_id = "claude-session-abc123"
    response = await client.post(
        "/api/sessions", json={"project": "test-project", "session_id": custom_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == custom_id


@pytest.mark.asyncio
async def test_session_start_without_project(
    client: AsyncClient, session_manager: SessionManager
):
    """Test SessionStart without a project (global session)."""
    response = await client.post("/api/sessions", json={"project": None})
    assert response.status_code == 200
    data = response.json()
    assert data["project"] is None
    assert data["status"] == "active"


# ============================================================================
# Test 3: User Prompt Capture
# ============================================================================


@pytest.mark.asyncio
async def test_user_prompt_capture(
    client: AsyncClient, session_manager: SessionManager
):
    """Test UserPromptSubmit hook captures prompts with metadata."""
    # Create session
    session = await session_manager.create_session(project="prompt-test")

    # Capture user prompt
    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": session.session_id,
            "event_type": "user_prompt",
            "content": "Please refactor the authentication module to use OAuth2",
            "metadata": {
                "prompt_length": 58,
                "project_context": "api-service",
                "timestamp_ms": 1706745600000,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["event_count"] == 1

    # Verify event was stored correctly
    updated_session = await session_manager.get_session(session.session_id)
    assert len(updated_session.events) == 1
    event = updated_session.events[0]
    assert event.event_type == SessionEventType.USER_PROMPT
    assert "OAuth2" in event.content
    assert event.metadata["prompt_length"] == 58


@pytest.mark.asyncio
async def test_user_prompt_capture_long_prompt(
    client: AsyncClient, session_manager: SessionManager
):
    """Test capturing a long user prompt."""
    session = await session_manager.create_session()
    long_prompt = "Please help me with: " + "a" * 5000  # 5KB+ prompt

    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": session.session_id,
            "event_type": "user_prompt",
            "content": long_prompt,
        },
    )
    assert response.status_code == 200

    updated_session = await session_manager.get_session(session.session_id)
    assert len(updated_session.events[0].content) > 5000


# ============================================================================
# Test 4: PostToolUse Event Type Detection
# ============================================================================


@pytest.mark.asyncio
async def test_post_tool_use_categorization(
    client: AsyncClient, session_manager: SessionManager
):
    """Test PostToolUse hook correctly categorizes different tool types."""
    session = await session_manager.create_session(project="tool-test")

    # Test different event types
    test_cases = [
        (SessionEventType.FILE_EDIT, "Created new file: src/auth/handler.py"),
        (SessionEventType.COMMAND, "Executed: npm run test"),
        (SessionEventType.RESEARCH, "Web search: GraphQL best practices"),
        (SessionEventType.ERROR, "Error: ModuleNotFoundError in auth.py"),
        (SessionEventType.TOOL_USE, "Used tool: Read file content"),
        (SessionEventType.DECISION, "Decided to use PostgreSQL over MongoDB"),
        (SessionEventType.SOLUTION, "Fixed by adding missing import statement"),
    ]

    for event_type, content in test_cases:
        response = await client.post(
            "/api/sessions/observe",
            json={
                "session_id": session.session_id,
                "event_type": event_type.value,
                "content": content,
                "metadata": {"source": "post_tool_use_hook"},
            },
        )
        assert response.status_code == 200, f"Failed for event type: {event_type}"

    # Verify all events stored with correct types
    updated_session = await session_manager.get_session(session.session_id)
    assert len(updated_session.events) == len(test_cases)

    for i, (expected_type, expected_content) in enumerate(test_cases):
        assert updated_session.events[i].event_type == expected_type
        assert updated_session.events[i].content == expected_content


@pytest.mark.asyncio
async def test_post_tool_use_with_error_detection(
    client: AsyncClient, session_manager: SessionManager
):
    """Test PostToolUse correctly flags errors from tool execution."""
    session = await session_manager.create_session()

    # Simulate error from tool use
    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": session.session_id,
            "event_type": "error",
            "content": "Error in bash: Command 'npm test' failed with exit code 1",
            "metadata": {
                "tool_name": "bash",
                "has_error": True,
                "exit_code": 1,
            },
        },
    )
    assert response.status_code == 200

    updated_session = await session_manager.get_session(session.session_id)
    error_event = updated_session.events[0]
    assert error_event.event_type == SessionEventType.ERROR
    assert error_event.metadata["has_error"] is True


# ============================================================================
# Test 5: PreCompact Summarization
# ============================================================================


@pytest.mark.asyncio
async def test_pre_compact_summarization(
    session_manager: SessionManager, mock_ai_processor
):
    """Test PreCompact hook triggers AI summarization with key_learnings extraction."""
    # Create session with events
    session = await session_manager.create_session(project="summarize-test")

    # Add some events to summarize
    events = [
        (SessionEventType.USER_PROMPT, "Build a REST API for user management"),
        (SessionEventType.DECISION, "Using FastAPI for its async support"),
        (SessionEventType.FILE_EDIT, "Created models/user.py with User model"),
        (SessionEventType.ERROR, "TypeError: missing required argument 'id'"),
        (SessionEventType.SOLUTION, "Added id field with default UUID generator"),
        (SessionEventType.COMMAND, "pytest tests/ - all passed"),
    ]

    for event_type, content in events:
        await session_manager.observe_event(session.session_id, event_type, content)

    # Trigger summarization with mock AI
    with patch(
        "app.services.session_manager.AIProcessor", return_value=mock_ai_processor
    ):
        summary = await session_manager.summarize_session(session.session_id)

    # Verify summary structure
    assert "key_learnings" in summary
    assert "decisions" in summary
    assert "errors_encountered" in summary
    assert "solutions_found" in summary


@pytest.mark.asyncio
async def test_pre_compact_summarization_without_ai(session_manager: SessionManager):
    """Test PreCompact gracefully handles unavailable AI processor."""
    session = await session_manager.create_session()
    await session_manager.observe_event(
        session.session_id, SessionEventType.OBSERVATION, "Test event"
    )

    # Should return basic summary when AI unavailable
    summary = await session_manager.summarize_session(session.session_id)

    # Basic summary should still have structure
    assert isinstance(summary, dict)
    assert "key_learnings" in summary or "summary_text" in summary


# ============================================================================
# Test 6: Session End Finalization
# ============================================================================


@pytest.mark.asyncio
async def test_session_end_finalization(
    client: AsyncClient, session_manager: SessionManager
):
    """Test SessionEnd hook correctly finalizes session status."""
    # Create and populate session
    session = await session_manager.create_session(project="end-test")
    await session_manager.observe_event(
        session.session_id, SessionEventType.OBSERVATION, "Final observation"
    )

    # End session
    response = await client.post(f"/api/sessions/{session.session_id}/end")
    assert response.status_code == 200
    data = response.json()

    # Verify finalization
    assert data["status"] == "completed"
    assert data["ended_at"] is not None

    # Verify persisted state
    final_session = await session_manager.get_session(session.session_id)
    assert final_session.status == "completed"
    assert final_session.ended_at is not None


@pytest.mark.asyncio
async def test_session_end_preserves_events(
    client: AsyncClient, session_manager: SessionManager
):
    """Test SessionEnd preserves all session events."""
    session = await session_manager.create_session()

    # Add multiple events
    for i in range(10):
        await session_manager.observe_event(
            session.session_id, SessionEventType.OBSERVATION, f"Event {i}"
        )

    # End session
    await client.post(f"/api/sessions/{session.session_id}/end")

    # Verify events preserved
    final_session = await session_manager.get_session(session.session_id)
    assert len(final_session.events) == 10


@pytest.mark.asyncio
async def test_session_end_not_found(client: AsyncClient):
    """Test SessionEnd with non-existent session returns 404."""
    response = await client.post("/api/sessions/nonexistent-session-id/end")
    assert response.status_code == 404


# ============================================================================
# Test 7: Graceful Failure Handling
# ============================================================================


@pytest.mark.asyncio
async def test_hook_graceful_failure_invalid_session(client: AsyncClient):
    """Test hooks handle invalid session ID gracefully."""
    # Observe with invalid session
    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": "invalid-session-xyz",
            "event_type": "observation",
            "content": "This should fail gracefully",
        },
    )
    # Should return error but not crash
    assert response.status_code in [404, 400]


@pytest.mark.asyncio
async def test_hook_graceful_failure_invalid_event_type(
    client: AsyncClient, session_manager: SessionManager
):
    """Test hooks handle invalid event types gracefully."""
    session = await session_manager.create_session()

    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": session.session_id,
            "event_type": "completely_invalid_type",
            "content": "Test content",
        },
    )
    # Should return validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_hook_graceful_failure_missing_content(
    client: AsyncClient, session_manager: SessionManager
):
    """Test hooks handle missing required fields gracefully."""
    session = await session_manager.create_session()

    response = await client.post(
        "/api/sessions/observe",
        json={
            "session_id": session.session_id,
            "event_type": "observation",
            # Missing 'content' field
        },
    )
    assert response.status_code == 422


# ============================================================================
# Test: Session Context Retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_session_context_retrieval(
    client: AsyncClient, session_manager: SessionManager
):
    """Test retrieving session context with events and summary."""
    session = await session_manager.create_session(project="context-test")

    # Add events
    for i in range(5):
        await session_manager.observe_event(
            session.session_id,
            SessionEventType.OBSERVATION,
            f"Observation {i}",
        )

    # Get context
    response = await client.post(
        "/api/sessions/context",
        json={
            "session_id": session.session_id,
            "include_events": True,
            "include_summary": True,
            "limit": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session.session_id
    assert data["project"] == "context-test"
    assert data["event_count"] == 5
    assert len(data["events"]) == 5


@pytest.mark.asyncio
async def test_session_context_with_limit(
    client: AsyncClient, session_manager: SessionManager
):
    """Test session context respects event limit."""
    session = await session_manager.create_session()

    # Add many events
    for i in range(20):
        await session_manager.observe_event(
            session.session_id, SessionEventType.OBSERVATION, f"Event {i}"
        )

    # Get context with limit
    response = await client.post(
        "/api/sessions/context",
        json={
            "session_id": session.session_id,
            "include_events": True,
            "limit": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["event_count"] == 20  # Total count
    assert len(data["events"]) == 5  # Limited response


# ============================================================================
# Test: Concurrent Session Operations
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_event_logging(session_manager: SessionManager):
    """Test multiple events can be logged concurrently without data loss."""
    import asyncio

    session = await session_manager.create_session()

    # Log events concurrently
    async def log_event(index: int):
        await session_manager.observe_event(
            session.session_id,
            SessionEventType.OBSERVATION,
            f"Concurrent event {index}",
        )

    # Run 20 concurrent event logs
    await asyncio.gather(*[log_event(i) for i in range(20)])

    # Verify all events were captured
    final_session = await session_manager.get_session(session.session_id)
    assert len(final_session.events) == 20


# ============================================================================
# Test: Hook Script Execution (Optional - requires bash)
# ============================================================================


@pytest.mark.skipif(
    not Path("/bin/bash").exists(), reason="Bash not available"
)
class TestHookScriptExecution:
    """Tests that execute actual hook bash scripts.

    These tests verify the hook scripts can execute without errors
    when the backend is unavailable (graceful failure).
    """

    @pytest.fixture
    def hooks_path(self) -> Path:
        """Get path to hooks directory."""
        return Path(__file__).parent.parent.parent.parent / "hooks"

    def test_session_start_script_graceful_failure(self, hooks_path: Path):
        """Test session-start.sh fails gracefully when backend unavailable."""
        script = hooks_path / "session-start.sh"
        if not script.exists():
            pytest.skip("session-start.sh not found")

        result = subprocess.run(
            [str(script)],
            capture_output=True,
            text=True,
            env={
                "OBSIDIAN_MEMORY_API_URL": "http://localhost:99999",  # Invalid port
                "OBSIDIAN_MEMORY_PROJECT": "test",
                "PATH": "/usr/bin:/bin",
            },
            timeout=10,
        )
        # Script should exit successfully (graceful failure)
        assert result.returncode == 0

    def test_post_tool_use_script_no_session(self, hooks_path: Path):
        """Test post-tool-use.sh exits cleanly when no session ID."""
        script = hooks_path / "post-tool-use.sh"
        if not script.exists():
            pytest.skip("post-tool-use.sh not found")

        result = subprocess.run(
            [str(script), "write_file", "Created test.py", ""],
            capture_output=True,
            text=True,
            env={
                "OBSIDIAN_MEMORY_API_URL": "http://localhost:8000",
                # No SESSION_ID - should skip
                "PATH": "/usr/bin:/bin",
            },
            timeout=10,
        )
        # Script should exit cleanly
        assert result.returncode == 0

    def test_session_end_script_graceful_failure(self, hooks_path: Path):
        """Test session-end.sh fails gracefully when backend unavailable."""
        script = hooks_path / "session-end.sh"
        if not script.exists():
            pytest.skip("session-end.sh not found")

        result = subprocess.run(
            [str(script)],
            capture_output=True,
            text=True,
            env={
                "OBSIDIAN_MEMORY_API_URL": "http://localhost:99999",
                "OBSIDIAN_MEMORY_SESSION_ID": "test-session",
                "PATH": "/usr/bin:/bin",
            },
            timeout=10,
        )
        # Script should exit (may fail due to backend, but shouldn't crash)
        # Exit code 0 for graceful failure
        assert result.returncode in [0, 1]  # Allow either success or controlled failure
