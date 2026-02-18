"""Tests for session deduplication and upsert semantics."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.models.session import SessionEvent, SessionEventType, SessionObserveRequest
from app.services.session_manager import SessionManager, generate_custom_id


class TestGenerateCustomId:
    """Test deterministic custom_id generation."""

    def test_deterministic_same_inputs(self):
        id1 = generate_custom_id('s1', SessionEventType.DECISION, 'content')
        id2 = generate_custom_id('s1', SessionEventType.DECISION, 'content')
        assert id1 == id2

    def test_different_content(self):
        id1 = generate_custom_id('s1', SessionEventType.DECISION, 'Use FastAPI')
        id2 = generate_custom_id('s1', SessionEventType.DECISION, 'Use Django')
        assert id1 != id2

    def test_different_event_type(self):
        id1 = generate_custom_id('s1', SessionEventType.DECISION, 'same')
        id2 = generate_custom_id('s1', SessionEventType.ERROR, 'same')
        assert id1 != id2

    def test_different_session_id(self):
        id1 = generate_custom_id('s1', SessionEventType.DECISION, 'same')
        id2 = generate_custom_id('s2', SessionEventType.DECISION, 'same')
        assert id1 != id2

    def test_format(self):
        cid = generate_custom_id('abc-123', SessionEventType.DECISION, 'Use X')
        assert cid.startswith('session_abc-123_decision_')
        # Hash portion should be 8 hex chars
        hash_part = cid.split('_')[-1]
        assert len(hash_part) == 8
        int(hash_part, 16)  # Should not raise - it's valid hex


class TestSessionEventModel:
    """Test SessionEvent model with custom_id fields."""

    def test_default_custom_id_none(self):
        event = SessionEvent(
            event_type=SessionEventType.DECISION,
            content='test',
        )
        assert event.custom_id is None
        assert event.updated_at is None

    def test_with_custom_id(self):
        event = SessionEvent(
            event_type=SessionEventType.DECISION,
            content='test',
            custom_id='my-custom-id',
        )
        assert event.custom_id == 'my-custom-id'

    def test_serialization_roundtrip(self):
        event = SessionEvent(
            event_type=SessionEventType.DECISION,
            content='test',
            custom_id='my-id',
            updated_at=datetime(2026, 1, 1),
        )
        data = event.model_dump()
        restored = SessionEvent(**data)
        assert restored.custom_id == 'my-id'
        assert restored.updated_at == datetime(2026, 1, 1)


class TestSessionObserveRequestModel:
    """Test SessionObserveRequest model with custom_id."""

    def test_default_custom_id_none(self):
        req = SessionObserveRequest(
            session_id='s1',
            event_type=SessionEventType.DECISION,
            content='test',
        )
        assert req.custom_id is None

    def test_with_custom_id(self):
        req = SessionObserveRequest(
            session_id='s1',
            event_type=SessionEventType.DECISION,
            content='test',
            custom_id='my-id',
        )
        assert req.custom_id == 'my-id'


@pytest.fixture
def session_manager(temp_dir: Path) -> SessionManager:
    """Create a SessionManager with temp storage."""
    return SessionManager(storage_path=temp_dir / 'sessions')


class TestObserveEventBackwardCompat:
    """Test backward compatibility: no custom_id = append-only."""

    @pytest.mark.asyncio
    async def test_append_without_custom_id(self, session_manager):
        session = await session_manager.create_session(session_id='s1')
        await session_manager.observe_event('s1', SessionEventType.DECISION, 'Alpha observation content')
        session = await session_manager.observe_event('s1', SessionEventType.DECISION, 'Alpha observation content')
        # Same content but no custom_id -> two separate events
        assert len(session.events) == 2
        assert session.events[0].custom_id is None
        assert session.events[1].custom_id is None

    @pytest.mark.asyncio
    async def test_events_without_custom_id_are_independent(self, session_manager):
        await session_manager.create_session(session_id='s1')
        await session_manager.observe_event('s1', SessionEventType.DECISION, 'Alpha observation')
        await session_manager.observe_event('s1', SessionEventType.DECISION, 'Bravo observation')
        session = await session_manager.observe_event('s1', SessionEventType.ERROR, 'Charlie error event')
        assert len(session.events) == 3


class TestObserveEventUpsert:
    """Test upsert behavior with custom_id."""

    @pytest.mark.asyncio
    async def test_insert_with_new_custom_id(self, session_manager):
        await session_manager.create_session(session_id='s1')
        session = await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Alpha decision content', custom_id='cid-1'
        )
        assert len(session.events) == 1
        assert session.events[0].custom_id == 'cid-1'
        assert session.events[0].content == 'Alpha decision content'

    @pytest.mark.asyncio
    async def test_update_with_existing_custom_id(self, session_manager):
        await session_manager.create_session(session_id='s1')
        await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Alpha decision content', custom_id='cid-1'
        )
        session = await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Alpha updated content', custom_id='cid-1'
        )
        assert len(session.events) == 1
        assert session.events[0].content == 'Alpha updated content'
        assert session.events[0].updated_at is not None

    @pytest.mark.asyncio
    async def test_upsert_preserves_original_timestamp(self, session_manager):
        await session_manager.create_session(session_id='s1')
        session = await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Alpha decision content', custom_id='cid-1'
        )
        original_ts = session.events[0].timestamp
        session = await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Bravo decision content', custom_id='cid-1'
        )
        assert session.events[0].timestamp == original_ts

    @pytest.mark.asyncio
    async def test_multiple_different_custom_ids(self, session_manager):
        await session_manager.create_session(session_id='s1')
        await session_manager.observe_event('s1', SessionEventType.DECISION, 'Alpha decision content', custom_id='cid-1')
        session = await session_manager.observe_event('s1', SessionEventType.ERROR, 'Bravo error content', custom_id='cid-2')
        assert len(session.events) == 2

    @pytest.mark.asyncio
    async def test_repeated_upsert_same_id(self, session_manager):
        await session_manager.create_session(session_id='s1')
        for i in range(10):
            session = await session_manager.observe_event(
                's1', SessionEventType.OBSERVATION, f'Version {i} of the observation', custom_id='cid-1'
            )
        assert len(session.events) == 1
        assert session.events[0].content == 'Version 9 of the observation'

    @pytest.mark.asyncio
    async def test_mixed_custom_id_and_append(self, session_manager):
        await session_manager.create_session(session_id='s1')
        await session_manager.observe_event('s1', SessionEventType.DECISION, 'No ID event first')
        await session_manager.observe_event('s1', SessionEventType.DECISION, 'Event with custom ID', custom_id='cid')
        session = await session_manager.observe_event('s1', SessionEventType.DECISION, 'No ID event second')
        assert len(session.events) == 3

    @pytest.mark.asyncio
    async def test_upsert_updates_metadata(self, session_manager):
        await session_manager.create_session(session_id='s1')
        await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Alpha decision content',
            metadata={'version': 1}, custom_id='cid-1'
        )
        session = await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Alpha decision content',
            metadata={'version': 2}, custom_id='cid-1'
        )
        assert session.events[0].metadata == {'version': 2}


class TestSessionPersistence:
    """Test that session data persists correctly with new fields."""

    @pytest.mark.asyncio
    async def test_persist_and_reload_with_custom_id(self, session_manager):
        await session_manager.create_session(session_id='s1')
        await session_manager.observe_event(
            's1', SessionEventType.DECISION, 'Alpha decision content', custom_id='cid-1'
        )
        # Clear cache to force disk reload
        session_manager._sessions.clear()
        session = await session_manager.get_session('s1')
        assert session.events[0].custom_id == 'cid-1'

    @pytest.mark.asyncio
    async def test_load_legacy_session_without_custom_id(self, session_manager):
        """Simulate loading a session file from before custom_id was added."""
        legacy_data = {
            "session_id": "legacy-1",
            "project": None,
            "started_at": "2026-01-01T00:00:00",
            "ended_at": None,
            "events": [
                {
                    "event_type": "decision",
                    "content": "Old event",
                    "timestamp": "2026-01-01T00:00:00",
                    "metadata": {},
                }
            ],
            "summary": None,
            "status": "active",
            "metadata": None,
        }
        session_file = session_manager.storage_path / "legacy-1.json"
        session_file.write_text(json.dumps(legacy_data))

        session = await session_manager.get_session('legacy-1')
        assert session is not None
        assert len(session.events) == 1
        assert session.events[0].custom_id is None
        assert session.events[0].updated_at is None

    @pytest.mark.asyncio
    async def test_session_not_found(self, session_manager):
        with pytest.raises(ValueError, match="not found"):
            await session_manager.observe_event(
                'nonexistent', SessionEventType.DECISION, 'A'
            )
