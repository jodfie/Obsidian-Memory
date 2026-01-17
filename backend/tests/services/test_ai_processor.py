"""Tests for AI processor service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.ai import (
    DeduplicationSuggestion,
    DeduplicationSuggestions,
    DetectedPattern,
    DetectedPatterns,
    Entity,
    EntityType,
    ExtractedEntities,
    InferredRelation,
    InferredRelations,
    SessionSummary,
)
from app.models.note import Frontmatter, NoteType, ParsedNote
from app.models.search import IndexedNote
from app.services.ai_processor import AIProcessor
from app.services.exceptions import AIProcessorError, AIProcessorUnavailableError


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client."""
    with patch("app.services.ai_processor.Anthropic") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield client_instance


@pytest.fixture
def ai_processor(mock_anthropic_client):
    """Create AI processor instance with mocked client."""
    return AIProcessor(
        api_key="test-api-key",
        model="claude-3-5-sonnet-20241022",
        max_retries=3,
        timeout_seconds=60,
    )


@pytest.fixture
def ai_processor_disabled():
    """Create disabled AI processor."""
    with patch("app.services.ai_processor.settings") as mock_settings:
        mock_settings.ai_processing_enabled = False
        mock_settings.anthropic_api_key = None
        return AIProcessor()


@pytest.fixture
def sample_parsed_note():
    """Sample parsed note for testing."""
    return ParsedNote(
        frontmatter=Frontmatter(
            title="Test Note",
            type=NoteType.NOTE,
            project="test-project",
        ),
        raw_content="This is a test note about FastAPI and SQLite.",
        observations=[],
        relations=[],
        wikilinks=[],
        headings=[],
    )


@pytest.fixture
def sample_indexed_note():
    """Sample indexed note for testing."""
    return IndexedNote(
        vault_name="test_vault",
        relative_path="test_note.md",
        title="Test Note",
        note_type="note",
        project="test-project",
        tags=[],
        content="This is a test note about FastAPI and SQLite.",
        file_hash="test_hash_123",
    )


class TestAIProcessorInitialization:
    """Test AI processor initialization."""

    def test_init_with_api_key(self, mock_anthropic_client):
        """Test initialization with API key."""
        with patch("app.services.ai_processor.Anthropic") as mock_anthropic:
            processor = AIProcessor(api_key="test-key")
            assert processor.api_key == "test-key"
            assert processor.enabled is True
            mock_anthropic.assert_called_once_with(api_key="test-key")

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch("app.services.ai_processor.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.ai_processing_enabled = True
            processor = AIProcessor()
            assert processor.enabled is False

    def test_init_disabled(self):
        """Test initialization when disabled."""
        with patch("app.services.ai_processor.settings") as mock_settings:
            mock_settings.ai_processing_enabled = False
            processor = AIProcessor()
            assert processor.enabled is False


class TestExtractEntities:
    """Test entity extraction."""

    @pytest.mark.asyncio
    async def test_extract_entities_success(self, ai_processor, mock_anthropic_client):
        """Test successful entity extraction."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"entities": [{"entity_type": "tool", "name": "FastAPI", "description": "Python web framework", "confidence": 1.0}, {"entity_type": "library", "name": "SQLite", "description": "Database", "confidence": 0.9}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_entities("This note mentions FastAPI and SQLite.")

        assert len(result.entities) == 2
        assert result.entities[0].entity_type == EntityType.TOOL
        assert result.entities[0].name == "FastAPI"
        assert result.entities[1].entity_type == EntityType.LIBRARY
        assert result.entities[1].name == "SQLite"

    @pytest.mark.asyncio
    async def test_extract_entities_with_markdown_code_block(
        self, ai_processor, mock_anthropic_client
    ):
        """Test entity extraction with JSON in markdown code block."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='```json\n{"entities": [{"entity_type": "tool", "name": "FastAPI", "confidence": 1.0}]}\n```',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_entities("Test content")

        assert len(result.entities) == 1
        assert result.entities[0].name == "FastAPI"

    @pytest.mark.asyncio
    async def test_extract_entities_unavailable(self, ai_processor_disabled):
        """Test entity extraction when AI is unavailable."""
        result = await ai_processor_disabled.extract_entities("Test content")
        assert len(result.entities) == 0

    @pytest.mark.asyncio
    async def test_extract_entities_api_error(self, ai_processor, mock_anthropic_client):
        """Test entity extraction with API error."""
        from anthropic import APIError
        import httpx

        mock_request = MagicMock(spec=httpx.Request)
        mock_anthropic_client.messages.create.side_effect = APIError(
            message="API error", request=mock_request, body=None
        )

        result = await ai_processor.extract_entities("Test content")
        # Should return empty result on error
        assert len(result.entities) == 0


class TestInferRelations:
    """Test relation inference."""

    @pytest.mark.asyncio
    async def test_infer_relations_success(
        self, ai_processor, mock_anthropic_client, sample_parsed_note, sample_indexed_note
    ):
        """Test successful relation inference."""
        note_pairs = [
            (sample_parsed_note, sample_indexed_note, sample_parsed_note, sample_indexed_note)
        ]

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"relations": [{"source_note_id": 0, "target_note_id": 0, "relation_type": "depends_on", "confidence": 0.9, "reasoning": "Note 0 depends on Note 1"}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.infer_relations(note_pairs)

        assert len(result.relations) == 1
        assert result.note_pairs_analyzed == 1
        assert result.relations[0].relation_type == "depends_on"

    @pytest.mark.asyncio
    async def test_infer_relations_empty(self, ai_processor):
        """Test relation inference with empty input."""
        result = await ai_processor.infer_relations([])
        assert len(result.relations) == 0
        assert result.note_pairs_analyzed == 0


class TestSummarizeSession:
    """Test session summarization."""

    @pytest.mark.asyncio
    async def test_summarize_session_success(self, ai_processor, mock_anthropic_client):
        """Test successful session summarization."""
        session_content = "Long session log with many details..."
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"key_learnings": ["Learned about FastAPI"], "decisions": ["Use async"], "errors_encountered": [], "solutions_found": [], "next_steps": [], "summary_text": "Session summary", "compression_ratio": 0.1}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.summarize_session(session_content)

        assert len(result.key_learnings) == 1
        assert len(result.decisions) == 1
        assert result.summary_text == "Session summary"
        assert result.compression_ratio > 0

    @pytest.mark.asyncio
    async def test_summarize_session_unavailable(self, ai_processor_disabled):
        """Test session summarization when AI is unavailable."""
        result = await ai_processor_disabled.summarize_session("Test session")
        assert result.summary_text == "AI processing unavailable"
        assert result.compression_ratio == 0.0


class TestDetectPatterns:
    """Test pattern detection."""

    @pytest.mark.asyncio
    async def test_detect_patterns_success(
        self, ai_processor, mock_anthropic_client, sample_parsed_note, sample_indexed_note
    ):
        """Test successful pattern detection."""
        notes = [(sample_parsed_note, sample_indexed_note)]

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"patterns": [{"pattern_name": "Test Pattern", "description": "A pattern", "note_ids": [0], "frequency": 1, "confidence": 0.9, "category": "solution"}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.detect_patterns(notes)

        assert len(result.patterns) == 1
        assert result.notes_analyzed == 1
        assert result.patterns[0].pattern_name == "Test Pattern"

    @pytest.mark.asyncio
    async def test_detect_patterns_empty(self, ai_processor):
        """Test pattern detection with empty input."""
        result = await ai_processor.detect_patterns([])
        assert len(result.patterns) == 0
        assert result.notes_analyzed == 0


class TestSuggestDeduplication:
    """Test deduplication suggestions."""

    @pytest.mark.asyncio
    async def test_suggest_deduplication_success(
        self, ai_processor, mock_anthropic_client, sample_parsed_note, sample_indexed_note
    ):
        """Test successful deduplication suggestion."""
        notes = [(sample_parsed_note, sample_indexed_note)]

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"suggestions": [{"note_ids": [0, 1], "similarity_score": 0.95, "reasoning": "Very similar content", "suggested_action": "merge"}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.suggest_deduplication(notes)

        assert len(result.suggestions) == 1
        assert result.notes_analyzed == 1
        assert result.suggestions[0].similarity_score == 0.95
        assert result.suggestions[0].suggested_action == "merge"

    @pytest.mark.asyncio
    async def test_suggest_deduplication_empty(self, ai_processor):
        """Test deduplication suggestion with empty input."""
        result = await ai_processor.suggest_deduplication([])
        assert len(result.suggestions) == 0
        assert result.notes_analyzed == 0


class TestRetryLogic:
    """Test retry logic for API calls."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, ai_processor, mock_anthropic_client):
        """Test retry on rate limit error."""
        from anthropic import RateLimitError
        import httpx

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = {}
        # First two calls fail with rate limit, third succeeds
        mock_anthropic_client.messages.create.side_effect = [
            RateLimitError(message="Rate limited", response=mock_response, body=None),
            RateLimitError(message="Rate limited", response=mock_response, body=None),
            MagicMock(
                content=[
                    MagicMock(
                        type="text",
                        text='{"entities": []}',
                    )
                ]
            ),
        ]

        result = await ai_processor.extract_entities("Test")
        # Should succeed after retries
        assert result is not None

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, ai_processor, mock_anthropic_client):
        """Test when max retries are exceeded."""
        from anthropic import APIError
        import httpx

        mock_request = MagicMock(spec=httpx.Request)
        mock_anthropic_client.messages.create.side_effect = APIError(
            message="API error", request=mock_request, body=None
        )

        # Should return empty result after max retries
        result = await ai_processor.extract_entities("Test")
        assert len(result.entities) == 0
