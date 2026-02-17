"""Tests for profile synthesis frequency tracker."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.profile_tracker import ProfileSynthesisTracker
from app.models.note import ProfileNote


@pytest.fixture
def tracker():
    """Create a tracker with frequency=3 for fast testing."""
    with patch("app.services.profile_tracker.settings") as mock_settings:
        mock_settings.profile_synthesis_frequency = 3
        mock_settings.profile_synthesis_enabled = True
        t = ProfileSynthesisTracker(frequency=3)
        yield t


@pytest.fixture
def mock_deps():
    """Create mock search_index and ai_processor."""
    search_index = AsyncMock()
    ai_processor = AsyncMock()
    ai_processor.synthesize_profile = AsyncMock(return_value=ProfileNote(
        project="test",
        static_facts=["fact1"],
        dynamic_patterns=["pattern1"],
        key_entities={"tools": ["pytest"]},
    ))
    return search_index, ai_processor


class TestWriteCountTracking:
    """Test write count increment and threshold detection."""

    @pytest.mark.asyncio
    async def test_increments_per_project(self, tracker, mock_deps):
        """Write count increments independently per project."""
        si, ai = mock_deps

        await tracker.record_write("project-a", si, ai)
        await tracker.record_write("project-b", si, ai)
        await tracker.record_write("project-a", si, ai)

        assert tracker.get_write_count("project-a") == 2
        assert tracker.get_write_count("project-b") == 1

    @pytest.mark.asyncio
    async def test_no_tracking_for_none_project(self, tracker, mock_deps):
        """None project is not tracked."""
        si, ai = mock_deps

        result = await tracker.record_write(None, si, ai)

        assert result is False
        assert tracker.get_write_count("") == 0

    @pytest.mark.asyncio
    async def test_disabled_tracker_noop(self, mock_deps):
        """Disabled tracker does nothing."""
        with patch("app.services.profile_tracker.settings") as mock_settings:
            mock_settings.profile_synthesis_frequency = 3
            mock_settings.profile_synthesis_enabled = False
            tracker = ProfileSynthesisTracker(frequency=3)
            tracker.enabled = False

        si, ai = mock_deps
        result = await tracker.record_write("proj", si, ai)

        assert result is False
        assert tracker.get_write_count("proj") == 0


class TestSynthesisTrigger:
    """Test synthesis trigger at threshold."""

    @pytest.mark.asyncio
    async def test_synthesis_triggered_at_threshold(self, tracker, mock_deps):
        """Synthesis fires exactly at frequency threshold."""
        si, ai = mock_deps

        # Writes 1 and 2: no synthesis
        r1 = await tracker.record_write("proj", si, ai)
        r2 = await tracker.record_write("proj", si, ai)
        assert r1 is False
        assert r2 is False

        # Write 3: triggers synthesis
        r3 = await tracker.record_write("proj", si, ai)
        assert r3 is True
        ai.synthesize_profile.assert_called_once_with("proj", si)

    @pytest.mark.asyncio
    async def test_counter_resets_after_synthesis(self, tracker, mock_deps):
        """Counter resets to 0 after successful synthesis."""
        si, ai = mock_deps

        # Trigger synthesis
        for _ in range(3):
            await tracker.record_write("proj", si, ai)

        assert tracker.get_write_count("proj") == 0

    @pytest.mark.asyncio
    async def test_synthesis_cycles(self, tracker, mock_deps):
        """Synthesis triggers again after counter resets."""
        si, ai = mock_deps

        # First cycle
        for _ in range(3):
            await tracker.record_write("proj", si, ai)
        assert ai.synthesize_profile.call_count == 1

        # Second cycle
        for _ in range(3):
            await tracker.record_write("proj", si, ai)
        assert ai.synthesize_profile.call_count == 2

    @pytest.mark.asyncio
    async def test_synthesis_error_doesnt_crash(self, tracker, mock_deps):
        """AI errors during synthesis don't crash the tracker."""
        si, ai = mock_deps
        ai.synthesize_profile = AsyncMock(side_effect=RuntimeError("AI down"))

        # Should not raise
        for _ in range(3):
            result = await tracker.record_write("proj", si, ai)

        # The final write tried synthesis but failed
        # Counter should NOT be reset since synthesis failed
        assert tracker.get_write_count("proj") == 3

    @pytest.mark.asyncio
    async def test_independent_project_counters(self, tracker, mock_deps):
        """Different projects have independent counters."""
        si, ai = mock_deps

        # Project A: 2 writes
        await tracker.record_write("proj-a", si, ai)
        await tracker.record_write("proj-a", si, ai)

        # Project B: 3 writes (triggers synthesis)
        for _ in range(3):
            await tracker.record_write("proj-b", si, ai)

        # Only proj-b triggered synthesis
        ai.synthesize_profile.assert_called_once_with("proj-b", si)
        assert tracker.get_write_count("proj-a") == 2
        assert tracker.get_write_count("proj-b") == 0


class TestConcurrency:
    """Test concurrent write handling."""

    @pytest.mark.asyncio
    async def test_no_duplicate_synthesis(self, tracker, mock_deps):
        """Concurrent writes don't trigger duplicate synthesis."""
        si, ai = mock_deps

        # Make synthesis slow
        async def slow_synthesis(project, search_index):
            await asyncio.sleep(0.1)
            return ProfileNote(project=project)

        ai.synthesize_profile = AsyncMock(side_effect=slow_synthesis)

        # Set count to threshold-1
        tracker._write_counts["proj"] = 2

        # Fire two writes simultaneously
        results = await asyncio.gather(
            tracker.record_write("proj", si, ai),
            tracker.record_write("proj", si, ai),
        )

        # Only one should trigger synthesis
        assert ai.synthesize_profile.call_count == 1

    @pytest.mark.asyncio
    async def test_reset_count_explicit(self, tracker):
        """Explicit reset_count works."""
        tracker._write_counts["proj"] = 42
        tracker.reset_count("proj")
        assert tracker.get_write_count("proj") == 0

    @pytest.mark.asyncio
    async def test_get_count_unknown_project(self, tracker):
        """Unknown project returns 0."""
        assert tracker.get_write_count("unknown") == 0
