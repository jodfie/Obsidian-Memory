"""Tests for decay management API endpoints."""

import pytest
from datetime import datetime, timezone

from app.services.search_index import SearchIndex


@pytest.fixture
async def db_path(tmp_path):
    """Return a temp DB path."""
    return tmp_path / "test_decay.db"


@pytest.fixture
async def search_index(db_path):
    """Create and initialize a SearchIndex."""
    index = SearchIndex(db_path)
    await index.initialize()
    yield index
    await index.close()


async def _seed_notes(search_index: SearchIndex) -> None:
    """Insert test notes with various decay_class and confidence values."""
    notes = [
        ("a.md", "Note A", "decision", "permanent", 1.0, None),
        ("b.md", "Note B", "decision", "permanent", 0.95, None),
        ("c.md", "Note C", "note", "stable", 0.8, "2026-06-01T00:00:00"),
        ("d.md", "Note D", "note", "stable", 0.7, "2026-06-01T00:00:00"),
        ("e.md", "Note E", "note", "stable", 0.6, "2026-06-01T00:00:00"),
        ("f.md", "Note F", "session", "active", 0.9, "2026-03-01T00:00:00"),
        ("g.md", "Note G", "session", "active", 0.3, "2026-03-01T00:00:00"),
        ("h.md", "Note H", "error", "active", 0.4, "2025-01-01T00:00:00"),  # expired
    ]
    for path, title, ntype, dclass, conf, exp in notes:
        await search_index.db.execute(
            "INSERT INTO notes (vault_name, relative_path, title, note_type, content, "
            "indexed_at, file_hash, decay_class, confidence, expires_at, last_accessed_at) "
            "VALUES ('test', ?, ?, ?, 'Content.', datetime('now'), ?, ?, ?, ?, datetime('now'))",
            (path, title, ntype, f"hash-{path}", dclass, conf, exp),
        )
    await search_index.db.commit()


async def _seed_observations(search_index: SearchIndex) -> None:
    """Insert decision-protected observations."""
    # Get note IDs for a.md and b.md
    cursor = await search_index.db.execute(
        "SELECT id FROM notes WHERE relative_path IN ('a.md', 'b.md')"
    )
    rows = await cursor.fetchall()
    for row in rows:
        await search_index.db.execute(
            "INSERT INTO observations (note_id, category, content, auto_extracted, decay_override) "
            "VALUES (?, 'decision', 'Test decision', 1, 'permanent')",
            (row["id"],),
        )
    await search_index.db.commit()


class TestRunDecay:
    """Test POST /api/notes/decay/run endpoint."""

    @pytest.mark.asyncio
    async def test_run_decay_returns_stats(self, search_index):
        """run_decay returns counts of decayed/protected/expired notes."""
        from app.api.decay import run_decay

        await _seed_notes(search_index)

        # Override dependency
        result = await run_decay(search_index=search_index)

        assert isinstance(result.decayed, int)
        assert isinstance(result.protected, int)
        assert isinstance(result.expired, int)
        assert "decayed" in result.message
        assert "protected" in result.message
        assert "expired" in result.message

    @pytest.mark.asyncio
    async def test_run_decay_empty_db(self, search_index):
        """run_decay handles empty database."""
        from app.api.decay import run_decay

        result = await run_decay(search_index=search_index)

        assert result.decayed == 0
        assert result.protected == 0
        assert result.expired == 0


class TestGetDecayStats:
    """Test GET /api/notes/decay/stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats_returns_all_fields(self, search_index):
        """get_decay_stats returns all breakdown fields."""
        from app.api.decay import get_decay_stats

        await _seed_notes(search_index)
        await _seed_observations(search_index)

        result = await get_decay_stats(search_index=search_index)

        # by_class should have keys for our inserted notes
        assert "permanent" in result.by_class
        assert "stable" in result.by_class
        assert "active" in result.by_class
        assert result.by_class["permanent"] == 2
        assert result.by_class["stable"] == 3
        assert result.by_class["active"] == 3

        # Expired notes (h.md has expires_at in the past)
        assert result.expired_count >= 1

        # Low confidence (g.md=0.3, h.md=0.4)
        assert result.low_confidence_count >= 2

        # Decision-protected (a.md and b.md have permanent observations)
        assert result.decision_protected_count == 2

        # Average confidence is a float
        assert 0.0 < result.average_confidence <= 1.0

    @pytest.mark.asyncio
    async def test_stats_empty_db(self, search_index):
        """Stats on empty database returns sensible defaults."""
        from app.api.decay import get_decay_stats

        result = await get_decay_stats(search_index=search_index)

        assert result.by_class == {}
        assert result.expired_count == 0
        assert result.low_confidence_count == 0
        assert result.decision_protected_count == 0
        assert result.average_confidence == 1.0  # AVG of nothing defaults to 1.0


class TestOverrideDecay:
    """Test PUT /api/notes/{note_id}/decay endpoint."""

    @pytest.mark.asyncio
    async def test_override_decay_class(self, search_index):
        """Override decay class recalculates expires_at."""
        from app.api.decay import override_decay, DecayOverrideRequest

        await _seed_notes(search_index)

        # Get note_id for c.md (currently 'stable')
        cursor = await search_index.db.execute(
            "SELECT id FROM notes WHERE relative_path = 'c.md'"
        )
        note_id = (await cursor.fetchone())["id"]

        request = DecayOverrideRequest(decay_class="active")
        result = await override_decay(note_id=note_id, request=request, search_index=search_index)

        assert result.note_id == note_id
        assert result.decay_class == "active"
        assert result.expires_at is not None

    @pytest.mark.asyncio
    async def test_override_confidence(self, search_index):
        """Override confidence value only."""
        from app.api.decay import override_decay, DecayOverrideRequest

        await _seed_notes(search_index)

        cursor = await search_index.db.execute(
            "SELECT id FROM notes WHERE relative_path = 'g.md'"
        )
        note_id = (await cursor.fetchone())["id"]

        request = DecayOverrideRequest(confidence=0.95)
        result = await override_decay(note_id=note_id, request=request, search_index=search_index)

        assert result.confidence == 0.95
        assert result.decay_class == "active"  # unchanged

    @pytest.mark.asyncio
    async def test_override_to_permanent(self, search_index):
        """Setting decay_class to permanent sets expires_at to None."""
        from app.api.decay import override_decay, DecayOverrideRequest

        await _seed_notes(search_index)

        cursor = await search_index.db.execute(
            "SELECT id FROM notes WHERE relative_path = 'f.md'"
        )
        note_id = (await cursor.fetchone())["id"]

        request = DecayOverrideRequest(decay_class="permanent")
        result = await override_decay(note_id=note_id, request=request, search_index=search_index)

        assert result.decay_class == "permanent"
        assert result.expires_at is None

    @pytest.mark.asyncio
    async def test_override_nonexistent_note(self, search_index):
        """Override on nonexistent note returns 404."""
        from app.api.decay import override_decay, DecayOverrideRequest
        from fastapi import HTTPException

        request = DecayOverrideRequest(decay_class="active")

        with pytest.raises(HTTPException) as exc_info:
            await override_decay(note_id=99999, request=request, search_index=search_index)

        assert exc_info.value.status_code == 404

    def test_invalid_confidence_rejected(self):
        """Pydantic rejects confidence outside [0.0, 1.0]."""
        from app.api.decay import DecayOverrideRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DecayOverrideRequest(confidence=1.5)

        with pytest.raises(ValidationError):
            DecayOverrideRequest(confidence=-0.1)

    def test_invalid_decay_class_rejected(self):
        """Pydantic rejects invalid decay_class values."""
        from app.api.decay import DecayOverrideRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DecayOverrideRequest(decay_class="invalid_class")

    @pytest.mark.asyncio
    async def test_override_persists_to_db(self, search_index):
        """Override values are actually persisted in the database."""
        from app.api.decay import override_decay, DecayOverrideRequest

        await _seed_notes(search_index)

        cursor = await search_index.db.execute(
            "SELECT id FROM notes WHERE relative_path = 'd.md'"
        )
        note_id = (await cursor.fetchone())["id"]

        request = DecayOverrideRequest(decay_class="session", confidence=0.5)
        await override_decay(note_id=note_id, request=request, search_index=search_index)

        # Verify directly in DB
        cursor = await search_index.db.execute(
            "SELECT decay_class, confidence FROM notes WHERE id = ?", (note_id,)
        )
        row = await cursor.fetchone()
        assert row["decay_class"] == "session"
        assert row["confidence"] == 0.5
