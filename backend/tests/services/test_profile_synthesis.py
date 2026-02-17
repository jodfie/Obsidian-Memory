"""Tests for AI-powered profile synthesis."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai_processor import AIProcessor
from app.models.note import ProfileNote


@pytest.fixture
def mock_ai_processor():
    """Create an AIProcessor with mocked Claude client."""
    with patch("app.services.ai_processor.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.anthropic_model = "claude-3-haiku-20240307"
        mock_settings.ai_max_retries = 1
        mock_settings.ai_timeout_seconds = 30
        mock_settings.ai_processing_enabled = True

        with patch("app.services.ai_processor.Anthropic"):
            processor = AIProcessor()
            yield processor


def _make_search_result(note_id, title, snippet, note_type="note", updated_at="2026-02-17T00:00:00"):
    """Create a mock search result."""
    result = MagicMock()
    result.note_id = note_id
    result.title = title
    result.snippet = snippet
    result.note_type = note_type
    result.updated_at = updated_at
    result.decay_class = "stable"
    result.confidence = 1.0
    return result


class TestSynthesizeProfile:
    """Test synthesize_profile() method."""

    @pytest.mark.asyncio
    async def test_empty_project_returns_empty_profile(self, mock_ai_processor):
        """Project with no notes returns empty profile."""
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=[])

        result = await mock_ai_processor.synthesize_profile("empty-project", mock_index)

        assert isinstance(result, ProfileNote)
        assert result.project == "empty-project"
        assert result.static_facts == []
        assert result.dynamic_patterns == []
        assert result.key_entities == {}
        assert result.synthesis_note_count == 0
        assert result.last_synthesized is not None

    @pytest.mark.asyncio
    async def test_successful_synthesis(self, mock_ai_processor):
        """Successful synthesis returns populated ProfileNote."""
        mock_results = [
            _make_search_result(1, "API Design", "Using FastAPI with async endpoints"),
            _make_search_result(2, "Database Setup", "SQLite with WAL mode for concurrency"),
            _make_search_result(3, "Testing Strategy", "pytest with async fixtures"),
        ]

        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=mock_results)

        mock_ai_processor._call_claude = AsyncMock(return_value='''{
            "static_facts": ["Uses FastAPI for web framework", "SQLite as primary database"],
            "dynamic_patterns": ["Focused on async patterns", "Writing comprehensive tests"],
            "key_entities": {
                "frameworks": ["FastAPI", "pytest"],
                "tools": ["SQLite"],
                "languages": ["Python"]
            }
        }''')

        result = await mock_ai_processor.synthesize_profile("test-project", mock_index)

        assert result.project == "test-project"
        assert len(result.static_facts) == 2
        assert "Uses FastAPI for web framework" in result.static_facts
        assert len(result.dynamic_patterns) == 2
        assert "frameworks" in result.key_entities
        assert "FastAPI" in result.key_entities["frameworks"]
        assert result.synthesis_note_count == 3
        assert result.profile_version == 1

    @pytest.mark.asyncio
    async def test_search_query_uses_project_filter(self, mock_ai_processor):
        """Verify the search query filters by project."""
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=[])

        await mock_ai_processor.synthesize_profile("my-project", mock_index)

        # Verify search was called with correct project filter
        mock_index.search.assert_called_once()
        query = mock_index.search.call_args[0][0]
        assert query.project == "my-project"
        assert query.query == "*"
        assert query.limit == 100

    @pytest.mark.asyncio
    async def test_custom_note_limit(self, mock_ai_processor):
        """Custom note_limit is passed through to search query."""
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=[])

        await mock_ai_processor.synthesize_profile("proj", mock_index, note_limit=50)

        query = mock_index.search.call_args[0][0]
        assert query.limit == 50

    @pytest.mark.asyncio
    async def test_ai_unavailable_returns_empty_profile(self, mock_ai_processor):
        """AIProcessorUnavailableError returns minimal profile."""
        from app.services.exceptions import AIProcessorUnavailableError

        mock_results = [_make_search_result(1, "Note", "Content")]
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=mock_results)

        mock_ai_processor._call_claude = AsyncMock(
            side_effect=AIProcessorUnavailableError("No API key")
        )

        result = await mock_ai_processor.synthesize_profile("proj", mock_index)

        assert result.project == "proj"
        assert result.static_facts == []
        assert result.dynamic_patterns == []
        assert result.synthesis_note_count == 1

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_empty_profile(self, mock_ai_processor):
        """Unexpected exceptions return minimal profile without raising."""
        mock_results = [_make_search_result(1, "Note", "Content")]
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=mock_results)

        mock_ai_processor._call_claude = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        result = await mock_ai_processor.synthesize_profile("proj", mock_index)

        assert result.project == "proj"
        assert result.static_facts == []
        assert result.synthesis_note_count == 1

    @pytest.mark.asyncio
    async def test_malformed_json_gracefully_handled(self, mock_ai_processor):
        """Malformed JSON from Claude is handled gracefully."""
        mock_results = [_make_search_result(1, "Note", "Content")]
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=mock_results)

        # _parse_json_response will raise on invalid JSON
        mock_ai_processor._call_claude = AsyncMock(return_value="not valid json at all")

        result = await mock_ai_processor.synthesize_profile("proj", mock_index)

        # Should return empty profile, not crash
        assert result.project == "proj"

    @pytest.mark.asyncio
    async def test_partial_json_fields(self, mock_ai_processor):
        """Partial JSON response (missing some fields) still works."""
        mock_results = [_make_search_result(1, "Note", "Content")]
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=mock_results)

        mock_ai_processor._call_claude = AsyncMock(return_value='{"static_facts": ["Prefers Python"]}')

        result = await mock_ai_processor.synthesize_profile("proj", mock_index)

        assert result.static_facts == ["Prefers Python"]
        assert result.dynamic_patterns == []
        assert result.key_entities == {}

    @pytest.mark.asyncio
    async def test_last_synthesized_is_set(self, mock_ai_processor):
        """last_synthesized timestamp is set on all return paths."""
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=[])

        before = datetime.now(timezone.utc)
        result = await mock_ai_processor.synthesize_profile("proj", mock_index)
        after = datetime.now(timezone.utc)

        assert result.last_synthesized is not None
        assert before <= result.last_synthesized <= after

    @pytest.mark.asyncio
    async def test_notes_truncated_in_prompt(self, mock_ai_processor):
        """Long note snippets are truncated to 500 chars in the prompt."""
        long_content = "x" * 1000
        mock_results = [_make_search_result(1, "Long Note", long_content)]
        mock_index = AsyncMock()
        mock_index.search = AsyncMock(return_value=mock_results)

        mock_ai_processor._call_claude = AsyncMock(return_value='{"static_facts": []}')

        await mock_ai_processor.synthesize_profile("proj", mock_index)

        # Check the user prompt passed to _call_claude
        call_args = mock_ai_processor._call_claude.call_args
        user_prompt = call_args[0][1]  # Second positional arg
        # The snippet should be truncated to 500 chars
        assert "x" * 501 not in user_prompt
