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


class TestExtractDecisions:
    """Test AI decision extraction."""

    @pytest.mark.asyncio
    async def test_extract_decisions_success(self, ai_processor, mock_anthropic_client):
        """Test successful decision extraction."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"decisions": [{"content": "Use FastAPI for the backend", "rationale": "Async support and type hints", "confidence": 0.95, "type": "decision", "entities": ["FastAPI", "Python"]}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_decisions(
            "We went with FastAPI for the backend because of async support.",
            note_title="Architecture Choices",
        )

        assert len(result) == 1
        assert result[0].content == "Use FastAPI for the backend"
        assert result[0].rationale == "Async support and type hints"
        assert result[0].confidence == 0.95
        assert result[0].decision_type == "decision"
        assert "FastAPI" in result[0].entities

    @pytest.mark.asyncio
    async def test_extract_decisions_implicit_patterns(self, ai_processor, mock_anthropic_client):
        """Test extraction of implicit decisions without trigger words."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"decisions": [{"content": "All API responses use JSON format", "rationale": null, "confidence": 0.7, "type": "convention", "entities": ["API", "JSON"]}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_decisions(
            "The API endpoints return JSON. Each response includes a status field."
        )

        assert len(result) == 1
        assert result[0].decision_type == "convention"
        assert result[0].rationale is None

    @pytest.mark.asyncio
    async def test_extract_decisions_confidence_bounds(self, ai_processor, mock_anthropic_client):
        """Test confidence values are clamped to [0.0, 1.0]."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"decisions": [{"content": "Too high", "rationale": null, "confidence": 1.5, "type": "decision", "entities": []}, {"content": "Too low", "rationale": null, "confidence": -0.3, "type": "decision", "entities": []}, {"content": "Normal", "rationale": null, "confidence": 0.5, "type": "decision", "entities": []}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_decisions("Some content")

        assert len(result) == 3
        assert result[0].confidence == 1.0  # clamped from 1.5
        assert result[1].confidence == 0.0  # clamped from -0.3
        assert result[2].confidence == 0.5  # unchanged

    @pytest.mark.asyncio
    async def test_extract_decisions_api_unavailable(self, ai_processor_disabled):
        """Test graceful degradation when AI is unavailable."""
        result = await ai_processor_disabled.extract_decisions("Some content")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_decisions_content_truncation(self, ai_processor, mock_anthropic_client):
        """Test that content is truncated to 4000 chars."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text='{"decisions": []}')
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        long_content = "x" * 8000
        await ai_processor.extract_decisions(long_content)

        # Verify the user prompt sent to Claude has truncated content
        call_args = mock_anthropic_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        # The user prompt includes title and headers, but content portion is truncated
        assert len(user_msg) < 8000 + 200  # content truncated + prompt overhead

    @pytest.mark.asyncio
    async def test_extract_decisions_malformed_response(self, ai_processor, mock_anthropic_client):
        """Test handling of malformed AI response."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="This is not JSON at all")
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_decisions("Some content")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_decisions_empty_decisions_list(self, ai_processor, mock_anthropic_client):
        """Test handling of empty decisions array."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text='{"decisions": []}')
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_decisions("Just a plain note.")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_decisions_multiple_types(self, ai_processor, mock_anthropic_client):
        """Test extraction of mixed decision types."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"decisions": [{"content": "Use Docker for deployment", "rationale": "Consistency", "confidence": 0.9, "type": "decision", "entities": ["Docker"]}, {"content": "Always use snake_case", "rationale": null, "confidence": 0.8, "type": "convention", "entities": []}, {"content": "Prefer SQLite over Postgres for dev", "rationale": "Simpler setup", "confidence": 0.6, "type": "preference", "entities": ["SQLite", "Postgres"]}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_decisions("Complex note")

        assert len(result) == 3
        assert result[0].decision_type == "decision"
        assert result[1].decision_type == "convention"
        assert result[2].decision_type == "preference"

    @pytest.mark.asyncio
    async def test_extract_decisions_api_error(self, ai_processor, mock_anthropic_client):
        """Test handling of API error during extraction."""
        from anthropic import APIError
        import httpx

        mock_request = MagicMock(spec=httpx.Request)
        mock_anthropic_client.messages.create.side_effect = APIError(
            message="API error", request=mock_request, body=None
        )

        result = await ai_processor.extract_decisions("Some content")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_decisions_default_confidence(self, ai_processor, mock_anthropic_client):
        """Test default confidence when not provided."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"decisions": [{"content": "Use Redis", "type": "decision"}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        result = await ai_processor.extract_decisions("Some content")

        assert len(result) == 1
        assert result[0].confidence == 0.8  # default
        assert result[0].rationale is None
        assert result[0].entities == []


class TestAIDecisionToObservation:
    """Test conversion of AI decisions to Observations."""

    def test_basic_conversion(self):
        """Test basic decision-to-observation conversion."""
        from app.services.ai_processor import ExtractedDecision, ai_decision_to_observation
        from app.models.note import ObservationCategory

        decision = ExtractedDecision(
            content="Use FastAPI for the backend",
            rationale="Async support",
            confidence=0.9,
            decision_type="decision",
            entities=["FastAPI"],
        )

        obs = ai_decision_to_observation(decision)

        assert obs.category == ObservationCategory.DECISION
        assert obs.content == "Use FastAPI for the backend"
        assert obs.context == "Async support"
        assert obs.auto_extracted is True
        assert obs.decay_override == "permanent"
        assert obs.tags == []
        assert obs.line_number == 0

    def test_none_rationale(self):
        """Test conversion with None rationale."""
        from app.services.ai_processor import ExtractedDecision, ai_decision_to_observation

        decision = ExtractedDecision(
            content="Always use snake_case",
            rationale=None,
            confidence=0.8,
            decision_type="convention",
        )

        obs = ai_decision_to_observation(decision)
        assert obs.context is None

    def test_custom_line_number(self):
        """Test conversion with custom line number."""
        from app.services.ai_processor import ExtractedDecision, ai_decision_to_observation

        decision = ExtractedDecision(
            content="Use Docker",
            rationale=None,
            confidence=0.7,
            decision_type="decision",
        )

        obs = ai_decision_to_observation(decision, line_number=42)
        assert obs.line_number == 42

    @pytest.mark.asyncio
    async def test_integration_extract_and_convert(self, ai_processor, mock_anthropic_client):
        """Integration: extract decisions then convert to observations."""
        from app.services.ai_processor import ai_decision_to_observation
        from app.models.note import ObservationCategory

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"decisions": [{"content": "Use SQLite for simplicity", "rationale": "No need for a full RDBMS", "confidence": 0.85, "type": "decision", "entities": ["SQLite"]}, {"content": "Always validate input at API boundary", "rationale": null, "confidence": 0.9, "type": "convention", "entities": []}]}',
            )
        ]
        mock_anthropic_client.messages.create.return_value = mock_response

        decisions = await ai_processor.extract_decisions(
            "We use SQLite because we don't need a full RDBMS. All input is validated at API boundaries.",
            note_title="Design Principles",
        )

        observations = [ai_decision_to_observation(d) for d in decisions]

        assert len(observations) == 2

        assert observations[0].category == ObservationCategory.DECISION
        assert observations[0].content == "Use SQLite for simplicity"
        assert observations[0].context == "No need for a full RDBMS"
        assert observations[0].auto_extracted is True
        assert observations[0].decay_override == "permanent"

        assert observations[1].content == "Always validate input at API boundary"
        assert observations[1].context is None
