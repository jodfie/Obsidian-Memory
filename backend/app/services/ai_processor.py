"""AI processor service for entity extraction, relation inference, and summarization."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from anthropic import Anthropic, APIError, RateLimitError

from app.config import settings
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
from app.models.note import ParsedNote, ProfileNote
from app.models.search import IndexedNote
from app.services.exceptions import AIProcessorError, AIProcessorUnavailableError

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDecision:
    """A decision extracted by AI analysis."""

    content: str
    rationale: str | None
    confidence: float
    decision_type: Literal['decision', 'convention', 'preference']
    entities: list[str] = field(default_factory=list)


def ai_decision_to_observation(
    decision: ExtractedDecision,
    line_number: int = 0,
) -> "Observation":
    """Convert an AI-extracted decision to an Observation model."""
    from app.models.note import Observation, ObservationCategory

    return Observation(
        category=ObservationCategory.DECISION,
        content=decision.content,
        tags=[],
        context=decision.rationale,
        line_number=line_number,
        auto_extracted=True,
        decay_override='permanent',
    )


class AIProcessor:
    """Service for AI-powered content processing using Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        """Initialize the AI processor.

        Args:
            api_key: Anthropic API key (defaults to settings.anthropic_api_key)
            model: Claude model to use (defaults to settings.anthropic_model)
            max_retries: Maximum retries for API calls (defaults to settings.ai_max_retries)
            timeout_seconds: Timeout for API calls (defaults to settings.ai_timeout_seconds)
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        self.max_retries = max_retries or settings.ai_max_retries
        self.timeout_seconds = timeout_seconds or settings.ai_timeout_seconds
        self.enabled = settings.ai_processing_enabled

        if not self.enabled:
            logger.warning("AI processing is disabled in settings")
            return

        if not self.api_key:
            logger.warning("Anthropic API key not configured")
            self.enabled = False
            return

        self.client = Anthropic(api_key=self.api_key)

    async def _call_claude(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
    ) -> str:
        """Make an async call to Claude API with retry logic.

        Args:
            system_prompt: System prompt for Claude
            user_prompt: User prompt with content to process
            max_tokens: Maximum tokens in response

        Returns:
            Response text from Claude

        Raises:
            AIProcessorUnavailableError: If AI processing is disabled
            AIProcessorError: If API call fails after retries
        """
        if not self.enabled:
            raise AIProcessorUnavailableError("AI processing is disabled")

        if not self.api_key:
            raise AIProcessorUnavailableError("Anthropic API key not configured")

        # Run the synchronous API call in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.messages.create(
                        model=self.model,
                        max_tokens=max_tokens,
                        system=system_prompt,
                        messages=[
                            {
                                "role": "user",
                                "content": user_prompt,
                            }
                        ],
                    ),
                )

                if response.content and len(response.content) > 0:
                    # Extract text from content blocks
                    text_parts = []
                    for block in response.content:
                        if block.type == "text":
                            text_parts.append(block.text)
                    return "\n".join(text_parts)

                raise AIProcessorError("Empty response from Claude API")

            except RateLimitError as e:
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Rate limit hit, retrying in {wait_time}s (attempt {attempt}/{self.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise AIProcessorError(f"Rate limit exceeded after {self.max_retries} retries") from e

            except APIError as e:
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"API error, retrying in {wait_time}s (attempt {attempt}/{self.max_retries}): {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise AIProcessorError(f"API call failed after {self.max_retries} retries: {e}") from e

            except Exception as e:
                raise AIProcessorError(f"Unexpected error calling Claude API: {e}") from e

        raise AIProcessorError(f"Failed after {self.max_retries} retries")

    def _parse_json_response(self, response_text: str) -> dict[str, Any]:
        """Parse JSON from Claude response, handling markdown code blocks.

        Args:
            response_text: Raw response text from Claude

        Returns:
            Parsed JSON dictionary

        Raises:
            AIProcessorError: If JSON parsing fails
        """
        # Try to extract JSON from markdown code blocks
        import re

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise AIProcessorError(f"Failed to parse JSON response: {e}") from e

    async def extract_entities(
        self,
        content: str,
        note_id: int | None = None,
    ) -> ExtractedEntities:
        """Extract entities (people, tools, concepts, errors) from note content.

        Args:
            content: Note content to analyze
            note_id: Optional note ID for tracking

        Returns:
            ExtractedEntities with list of entities found
        """
        system_prompt = """You are an entity extraction system. Analyze the provided content and extract entities such as:
- People (developers, users, authors)
- Tools (software, libraries, frameworks, CLIs)
- Concepts (patterns, techniques, ideas)
- Errors (error messages, exceptions, failures)
- Libraries and frameworks
- Projects and files
- Commands

Return a JSON object with an "entities" array. Each entity should have:
- entity_type: one of person, tool, concept, error, library, framework, pattern, technique, project, file, command
- name: the entity name
- description: brief description or context (optional)
- confidence: confidence score 0-1 (optional, default 1.0)

Example:
{
  "entities": [
    {
      "entity_type": "tool",
      "name": "FastAPI",
      "description": "Python web framework",
      "confidence": 1.0
    },
    {
      "entity_type": "error",
      "name": "sqlite3.OperationalError",
      "description": "Database operation failed",
      "confidence": 0.9
    }
  ]
}"""

        user_prompt = f"Extract entities from the following content:\n\n{content}"

        try:
            response = await self._call_claude(system_prompt, user_prompt)
            data = self._parse_json_response(response)

            entities = []
            for item in data.get("entities", []):
                try:
                    entity = Entity(**item)
                    entities.append(entity)
                except Exception as e:
                    logger.warning(f"Failed to parse entity: {item}, error: {e}")

            return ExtractedEntities(entities=entities, note_id=note_id)

        except AIProcessorUnavailableError:
            # Return empty result if AI is unavailable
            return ExtractedEntities(entities=[], note_id=note_id)
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return ExtractedEntities(entities=[], note_id=note_id)

    async def infer_relations(
        self,
        note_pairs: list[tuple[ParsedNote, IndexedNote, ParsedNote, IndexedNote]],
    ) -> InferredRelations:
        """Automatically infer relations between pairs of notes.

        Args:
            note_pairs: List of tuples (parsed_note1, indexed_note1, parsed_note2, indexed_note2)

        Returns:
            InferredRelations with list of inferred relations
        """
        if not note_pairs:
            return InferredRelations(relations=[], note_pairs_analyzed=0)

        system_prompt = """You are a relation inference system. Analyze pairs of notes and determine if there are semantic relationships between them.

Possible relation types:
- depends_on: Note A depends on Note B
- enables: Note A enables Note B
- related_to: General relatedness
- learned_from: Note A learned from Note B
- supersedes: Note A supersedes Note B
- caused_by: Note A was caused by Note B
- solved_by: Note A's problem was solved by Note B
- part_of: Note A is part of Note B
- implements: Note A implements Note B
- tests: Note A tests Note B
- documents: Note A documents Note B

Return a JSON object with a "relations" array. Each relation should have:
- source_note_id: ID of source note (use 0-based index from pairs)
- target_note_id: ID of target note (use 0-based index from pairs)
- relation_type: one of the relation types above
- confidence: confidence score 0-1
- reasoning: brief explanation (optional)

Example:
{
  "relations": [
    {
      "source_note_id": 0,
      "target_note_id": 1,
      "relation_type": "depends_on",
      "confidence": 0.9,
      "reasoning": "Note 0 explicitly mentions using concepts from Note 1"
    }
  ]
}"""

        # Format note pairs for analysis
        pairs_text = []
        for idx, (parsed1, indexed1, parsed2, indexed2) in enumerate(note_pairs):
            pairs_text.append(
                f"Pair {idx}:\n"
                f"Note 1 (ID {idx*2}): {parsed1.frontmatter.title}\n"
                f"Content: {parsed1.raw_content[:500]}...\n"
                f"Note 2 (ID {idx*2+1}): {parsed2.frontmatter.title}\n"
                f"Content: {parsed2.raw_content[:500]}...\n"
            )

        user_prompt = f"Analyze these note pairs and infer relations:\n\n{''.join(pairs_text)}"

        try:
            response = await self._call_claude(system_prompt, user_prompt)
            data = self._parse_json_response(response)

            relations = []
            for item in data.get("relations", []):
                try:
                    # Map 0-based indices back to actual note IDs
                    # Each pair has 2 notes, so max index is len(note_pairs) * 2 - 1
                    source_idx = item.get("source_note_id", 0)
                    target_idx = item.get("target_note_id", 0)
                    max_index = len(note_pairs) * 2
                    if source_idx < max_index and target_idx < max_index:
                        # For now, use the index as a placeholder
                        # In real implementation, would need actual note IDs from IndexedNote
                        relation = InferredRelation(
                            source_note_id=source_idx,
                            target_note_id=target_idx,
                            relation_type=item.get("relation_type", "related_to"),
                            confidence=item.get("confidence", 1.0),
                            reasoning=item.get("reasoning"),
                        )
                        relations.append(relation)
                except Exception as e:
                    logger.warning(f"Failed to parse relation: {item}, error: {e}")

            return InferredRelations(
                relations=relations, note_pairs_analyzed=len(note_pairs)
            )

        except AIProcessorUnavailableError:
            return InferredRelations(relations=[], note_pairs_analyzed=len(note_pairs))
        except Exception as e:
            logger.error(f"Error inferring relations: {e}")
            return InferredRelations(relations=[], note_pairs_analyzed=len(note_pairs))

    async def summarize_session(
        self,
        session_content: str,
        max_length: int = 1000,
    ) -> SessionSummary:
        """Summarize a session log into key learnings.

        Args:
            session_content: Full session log content
            max_length: Maximum length of summary text

        Returns:
            SessionSummary with key learnings, decisions, errors, etc.
        """
        system_prompt = """You are a session summarization system. Analyze a session log and extract:
- Key learnings (important insights, discoveries)
- Decisions made (architectural, implementation choices)
- Errors encountered (problems, failures)
- Solutions found (how errors were resolved)
- Next steps (suggested actions)
- Topics (main themes/subjects discussed)
- Participants (people, tools, systems, libraries involved)
- Actionable items (concrete follow-up tasks)
- Related notes (suggested references like "debugging-guide", "api-patterns")

Return a JSON object with:
- key_learnings: array of strings
- decisions: array of strings
- errors_encountered: array of strings
- solutions_found: array of strings
- next_steps: array of strings
- topics: array of strings (main themes)
- participants: array of strings (entities involved)
- actionable_items: array of strings (follow-up tasks)
- related_notes: array of strings (suggested note references)
- summary_text: overall summary (max {max_length} chars)
- compression_ratio: ratio of summary length to original length

Example:
{{
  "key_learnings": ["FastAPI requires async dependencies", "SQLite FTS5 has limitations"],
  "decisions": ["Use httpx.AsyncClient for tests", "Store content separately from FTS"],
  "errors_encountered": ["sqlite3.OperationalError: no such column"],
  "solutions_found": ["Use DELETE+INSERT for FTS updates"],
  "next_steps": ["Add content caching", "Implement retry logic"],
  "topics": ["database", "testing", "async-patterns"],
  "participants": ["SQLite", "FastAPI", "pytest"],
  "actionable_items": ["Create FTS update helper function", "Add retry decorator"],
  "related_notes": ["sqlite-fts-guide", "async-testing-patterns"],
  "summary_text": "Session focused on fixing SQLite FTS5 issues...",
  "compression_ratio": 0.15
}}""".format(
            max_length=max_length
        )

        user_prompt = f"Summarize this session:\n\n{session_content}"

        try:
            response = await self._call_claude(system_prompt, user_prompt, max_tokens=2048)
            data = self._parse_json_response(response)

            original_length = len(session_content)
            summary_text = data.get("summary_text", "")[:max_length]
            compression_ratio = (
                len(summary_text) / original_length if original_length > 0 else 0.0
            )

            return SessionSummary(
                key_learnings=data.get("key_learnings", []),
                decisions=data.get("decisions", []),
                errors_encountered=data.get("errors_encountered", []),
                solutions_found=data.get("solutions_found", []),
                next_steps=data.get("next_steps", []),
                topics=data.get("topics", []),
                participants=data.get("participants", []),
                actionable_items=data.get("actionable_items", []),
                related_notes=data.get("related_notes", []),
                summary_text=summary_text,
                compression_ratio=compression_ratio,
            )

        except AIProcessorUnavailableError:
            # Return minimal summary if AI unavailable
            return SessionSummary(
                key_learnings=[],
                decisions=[],
                errors_encountered=[],
                solutions_found=[],
                next_steps=[],
                summary_text="AI processing unavailable",
                compression_ratio=0.0,
            )
        except Exception as e:
            logger.error(f"Error summarizing session: {e}")
            return SessionSummary(
                key_learnings=[],
                decisions=[],
                errors_encountered=[],
                solutions_found=[],
                next_steps=[],
                summary_text=f"Error: {e}",
                compression_ratio=0.0,
            )

    async def summarize_session_incremental(
        self,
        event_chunks: list[str],
        max_length: int = 1000,
    ) -> SessionSummary:
        """Incrementally summarize a session by processing chunks.

        For long sessions, this method:
        1. Summarizes each chunk independently
        2. Creates a meta-summary combining all chunk summaries

        Args:
            event_chunks: List of event content chunks
            max_length: Maximum length of final summary text

        Returns:
            SessionSummary with combined results and chunk_count/is_incremental set
        """
        if len(event_chunks) <= 1:
            # Single chunk - use regular summarization
            content = event_chunks[0] if event_chunks else ""
            summary = await self.summarize_session(content, max_length)
            return summary

        # Summarize each chunk
        chunk_summaries: list[SessionSummary] = []
        for i, chunk in enumerate(event_chunks):
            logger.info(f"Summarizing chunk {i + 1}/{len(event_chunks)}")
            chunk_summary = await self.summarize_session(chunk, max_length=500)
            chunk_summaries.append(chunk_summary)

        # Combine chunk summaries into meta-summary
        return await self._combine_chunk_summaries(
            chunk_summaries, max_length, len(event_chunks)
        )

    async def _combine_chunk_summaries(
        self,
        chunk_summaries: list[SessionSummary],
        max_length: int,
        chunk_count: int,
    ) -> SessionSummary:
        """Combine multiple chunk summaries into a final summary.

        Args:
            chunk_summaries: List of chunk summaries
            max_length: Maximum length of final summary text
            chunk_count: Number of original chunks

        Returns:
            Combined SessionSummary
        """
        # Prepare combined content for meta-summarization
        combined_content = []
        for i, summary in enumerate(chunk_summaries):
            combined_content.append(f"=== Chunk {i + 1} Summary ===")
            combined_content.append(f"Summary: {summary.summary_text}")
            if summary.key_learnings:
                combined_content.append(f"Key learnings: {', '.join(summary.key_learnings)}")
            if summary.decisions:
                combined_content.append(f"Decisions: {', '.join(summary.decisions)}")
            if summary.errors_encountered:
                combined_content.append(f"Errors: {', '.join(summary.errors_encountered)}")
            if summary.topics:
                combined_content.append(f"Topics: {', '.join(summary.topics)}")
            combined_content.append("")

        meta_content = "\n".join(combined_content)

        system_prompt = """You are creating a meta-summary from multiple chunk summaries.
Combine and deduplicate the information into a cohesive final summary.

Return a JSON object with:
- key_learnings: array of unique key learnings (deduplicated)
- decisions: array of unique decisions
- errors_encountered: array of unique errors
- solutions_found: array of unique solutions
- next_steps: array of prioritized next steps
- topics: array of main topics across all chunks
- participants: array of all participants mentioned
- actionable_items: array of actionable items (prioritized)
- related_notes: array of suggested note references
- summary_text: cohesive overall summary (max {max_length} chars)
- compression_ratio: estimated compression ratio

Focus on deduplication and synthesis rather than simple concatenation.""".format(
            max_length=max_length
        )

        user_prompt = f"Create a meta-summary from these chunk summaries:\n\n{meta_content}"

        try:
            response = await self._call_claude(system_prompt, user_prompt, max_tokens=2048)
            data = self._parse_json_response(response)

            return SessionSummary(
                key_learnings=data.get("key_learnings", []),
                decisions=data.get("decisions", []),
                errors_encountered=data.get("errors_encountered", []),
                solutions_found=data.get("solutions_found", []),
                next_steps=data.get("next_steps", []),
                topics=data.get("topics", []),
                participants=data.get("participants", []),
                actionable_items=data.get("actionable_items", []),
                related_notes=data.get("related_notes", []),
                summary_text=data.get("summary_text", "")[:max_length],
                compression_ratio=data.get("compression_ratio", 0.0),
                chunk_count=chunk_count,
                is_incremental=True,
            )

        except Exception as e:
            logger.error(f"Error creating meta-summary: {e}")
            # Fallback: combine results manually
            return self._fallback_combine_summaries(chunk_summaries, chunk_count)

    def _fallback_combine_summaries(
        self,
        chunk_summaries: list[SessionSummary],
        chunk_count: int,
    ) -> SessionSummary:
        """Fallback method to combine summaries without AI.

        Simply concatenates and deduplicates lists from all chunks.

        Args:
            chunk_summaries: List of chunk summaries
            chunk_count: Number of original chunks

        Returns:
            Combined SessionSummary
        """
        # Helper to deduplicate while preserving order
        def dedupe(items: list[str]) -> list[str]:
            seen = set()
            result = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
            return result

        # Combine all lists
        all_learnings = []
        all_decisions = []
        all_errors = []
        all_solutions = []
        all_next_steps = []
        all_topics = []
        all_participants = []
        all_actionable = []
        all_related = []
        summary_parts = []

        for summary in chunk_summaries:
            all_learnings.extend(summary.key_learnings)
            all_decisions.extend(summary.decisions)
            all_errors.extend(summary.errors_encountered)
            all_solutions.extend(summary.solutions_found)
            all_next_steps.extend(summary.next_steps)
            all_topics.extend(summary.topics)
            all_participants.extend(summary.participants)
            all_actionable.extend(summary.actionable_items)
            all_related.extend(summary.related_notes)
            if summary.summary_text:
                summary_parts.append(summary.summary_text)

        # Combine summary texts
        combined_text = " | ".join(summary_parts[:3])  # Limit to avoid overflow
        if len(summary_parts) > 3:
            combined_text += f" ... (+{len(summary_parts) - 3} more chunks)"

        return SessionSummary(
            key_learnings=dedupe(all_learnings)[:10],
            decisions=dedupe(all_decisions)[:10],
            errors_encountered=dedupe(all_errors)[:10],
            solutions_found=dedupe(all_solutions)[:10],
            next_steps=dedupe(all_next_steps)[:10],
            topics=dedupe(all_topics)[:10],
            participants=dedupe(all_participants)[:10],
            actionable_items=dedupe(all_actionable)[:10],
            related_notes=dedupe(all_related)[:10],
            summary_text=combined_text[:1000],
            compression_ratio=0.0,
            chunk_count=chunk_count,
            is_incremental=True,
        )

    async def detect_patterns(
        self,
        notes: list[tuple[ParsedNote, IndexedNote]],
    ) -> DetectedPatterns:
        """Detect recurring patterns across multiple notes.

        Args:
            notes: List of tuples (parsed_note, indexed_note)

        Returns:
            DetectedPatterns with list of detected patterns
        """
        if not notes:
            return DetectedPatterns(patterns=[], notes_analyzed=0)

        system_prompt = """You are a pattern detection system. Analyze multiple notes and identify recurring patterns such as:
- Common solutions to similar problems
- Repeated techniques or approaches
- Similar error patterns
- Common architectural decisions
- Recurring implementation patterns

Return a JSON object with a "patterns" array. Each pattern should have:
- pattern_name: descriptive name
- description: what the pattern represents
- note_ids: array of note indices (0-based) that exhibit this pattern
- frequency: number of occurrences
- confidence: confidence score 0-1
- category: optional category (solution, technique, error, etc.)

Example:
{
  "patterns": [
    {
      "pattern_name": "FTS5 Update Pattern",
      "description": "Using DELETE+INSERT instead of UPDATE for FTS5 tables",
      "note_ids": [0, 3, 5],
      "frequency": 3,
      "confidence": 0.95,
      "category": "solution"
    }
  ]
}"""

        # Format notes for analysis
        notes_text = []
        for idx, (parsed, indexed) in enumerate(notes):
            notes_text.append(
                f"Note {idx}: {parsed.frontmatter.title}\n"
                f"Type: {parsed.frontmatter.type}\n"
                f"Content: {parsed.raw_content[:500]}...\n"
            )

        user_prompt = f"Detect patterns across these notes:\n\n{''.join(notes_text)}"

        try:
            response = await self._call_claude(system_prompt, user_prompt, max_tokens=2048)
            data = self._parse_json_response(response)

            patterns = []
            for item in data.get("patterns", []):
                try:
                    pattern = DetectedPattern(
                        pattern_name=item.get("pattern_name", "Unknown Pattern"),
                        description=item.get("description", ""),
                        note_ids=item.get("note_ids", []),
                        frequency=item.get("frequency", len(item.get("note_ids", []))),
                        confidence=item.get("confidence", 1.0),
                        category=item.get("category"),
                    )
                    patterns.append(pattern)
                except Exception as e:
                    logger.warning(f"Failed to parse pattern: {item}, error: {e}")

            return DetectedPatterns(patterns=patterns, notes_analyzed=len(notes))

        except AIProcessorUnavailableError:
            return DetectedPatterns(patterns=[], notes_analyzed=len(notes))
        except Exception as e:
            logger.error(f"Error detecting patterns: {e}")
            return DetectedPatterns(patterns=[], notes_analyzed=len(notes))

    async def suggest_deduplication(
        self,
        notes: list[tuple[ParsedNote, IndexedNote]],
    ) -> DeduplicationSuggestions:
        """Suggest duplicate notes that could be merged or linked.

        Args:
            notes: List of tuples (parsed_note, indexed_note)

        Returns:
            DeduplicationSuggestions with list of suggestions
        """
        if not notes:
            return DeduplicationSuggestions(suggestions=[], notes_analyzed=0)

        system_prompt = """You are a deduplication analysis system. Analyze notes and identify potential duplicates that could be merged or linked.

Return a JSON object with a "suggestions" array. Each suggestion should have:
- note_ids: array of note indices (0-based) that are duplicates
- similarity_score: similarity score 0-1
- reasoning: why these notes are considered duplicates
- suggested_action: one of "merge", "link", or "keep_separate"

Example:
{
  "suggestions": [
    {
      "note_ids": [0, 2],
      "similarity_score": 0.92,
      "reasoning": "Both notes describe the same solution to FTS5 update issues",
      "suggested_action": "merge"
    }
  ]
}"""

        # Format notes for analysis
        notes_text = []
        for idx, (parsed, indexed) in enumerate(notes):
            notes_text.append(
                f"Note {idx}: {parsed.frontmatter.title}\n"
                f"Content: {parsed.raw_content[:500]}...\n"
            )

        user_prompt = f"Analyze these notes for duplicates:\n\n{''.join(notes_text)}"

        try:
            response = await self._call_claude(system_prompt, user_prompt, max_tokens=2048)
            data = self._parse_json_response(response)

            suggestions = []
            for item in data.get("suggestions", []):
                try:
                    suggestion = DeduplicationSuggestion(
                        note_ids=item.get("note_ids", []),
                        similarity_score=item.get("similarity_score", 0.0),
                        reasoning=item.get("reasoning", ""),
                        suggested_action=item.get("suggested_action", "keep_separate"),
                    )
                    suggestions.append(suggestion)
                except Exception as e:
                    logger.warning(f"Failed to parse suggestion: {item}, error: {e}")

            return DeduplicationSuggestions(
                suggestions=suggestions, notes_analyzed=len(notes)
            )

        except AIProcessorUnavailableError:
            return DeduplicationSuggestions(suggestions=[], notes_analyzed=len(notes))
        except Exception as e:
            logger.error(f"Error suggesting deduplication: {e}")
            return DeduplicationSuggestions(suggestions=[], notes_analyzed=len(notes))

    async def synthesize_profile(
        self,
        project: str,
        search_index: Any,
        note_limit: int = 100,
    ) -> ProfileNote:
        """Synthesize a user/project profile from recent memory notes.

        Queries recent notes for the given project, sends them to Claude for
        analysis, and returns a structured ProfileNote with static facts,
        dynamic patterns, and key entities.

        Args:
            project: Project identifier to synthesize profile for
            search_index: SearchIndex instance for querying notes
            note_limit: Maximum number of notes to analyze

        Returns:
            ProfileNote with synthesized profile data
        """
        from app.models.search import SearchQuery, SortOrder

        # Query recent notes for this project
        query = SearchQuery(
            query="*",
            project=project,
            sort=SortOrder.UPDATED_DESC,
            limit=note_limit,
        )
        results = await search_index.search(query)

        if not results:
            logger.info(f"No notes found for project '{project}', returning empty profile")
            return ProfileNote(
                project=project,
                last_synthesized=datetime.now(timezone.utc),
                synthesis_note_count=0,
            )

        # Format notes for Claude analysis
        notes_text = []
        for r in results:
            notes_text.append(
                f"--- Note: {r.title} (type: {r.note_type}, updated: {r.updated_at}) ---\n"
                f"{r.snippet[:500]}\n"
            )

        notes_content = "\n".join(notes_text)

        system_prompt = """You are a profile synthesis system for a knowledge management tool.
Analyze the provided notes and extract a structured profile for the project/user.

Extract three categories of information:

1. **static_facts**: Stable, persistent facts and preferences that don't change often.
   Examples: preferred language, tech stack, team size, architecture choices, coding style preferences.

2. **dynamic_patterns**: Recent behavioral patterns, focus areas, and recurring themes.
   Examples: "Currently focused on performance optimization", "Frequently debugging async issues",
   "Writing many tests for API endpoints".

3. **key_entities**: Categorized important entities mentioned across notes.
   Categories: tools, languages, frameworks, people, services, concepts.
   Example: {"tools": ["Docker", "pytest"], "frameworks": ["FastAPI", "React"]}

Return a JSON object:
{
  "static_facts": ["fact1", "fact2", ...],
  "dynamic_patterns": ["pattern1", "pattern2", ...],
  "key_entities": {
    "tools": ["tool1", "tool2"],
    "languages": ["lang1"],
    "frameworks": ["fw1"],
    "people": ["person1"],
    "services": ["svc1"],
    "concepts": ["concept1"]
  }
}

Rules:
- Keep facts concise (one sentence each)
- Limit to 10-15 static facts, 5-10 dynamic patterns
- Only include entities that appear in multiple notes or are clearly central
- Omit empty entity categories"""

        user_prompt = f"Synthesize a profile for project '{project}' from these {len(results)} notes:\n\n{notes_content}"

        try:
            response = await self._call_claude(system_prompt, user_prompt, max_tokens=2048)
            data = self._parse_json_response(response)

            return ProfileNote(
                project=project,
                static_facts=data.get("static_facts", []),
                dynamic_patterns=data.get("dynamic_patterns", []),
                key_entities=data.get("key_entities", {}),
                profile_version=1,
                last_synthesized=datetime.now(timezone.utc),
                synthesis_note_count=len(results),
            )

        except AIProcessorUnavailableError:
            logger.warning(f"AI unavailable for profile synthesis of project '{project}'")
            return ProfileNote(
                project=project,
                last_synthesized=datetime.now(timezone.utc),
                synthesis_note_count=len(results),
            )
        except Exception as e:
            logger.error(f"Error synthesizing profile for project '{project}': {e}")
            return ProfileNote(
                project=project,
                last_synthesized=datetime.now(timezone.utc),
                synthesis_note_count=len(results),
            )

    async def extract_decisions(
        self,
        content: str,
        note_title: str | None = None,
    ) -> list[ExtractedDecision]:
        """Extract decisions, conventions, and preferences using Claude AI.

        Finds implicit decisions that regex patterns miss.
        Cost: ~500-1000 tokens per note (~$0.002/note with Sonnet).

        Args:
            content: Note content to analyze.
            note_title: Optional title for context.

        Returns:
            List of extracted decisions (empty on error or AI unavailable).
        """
        system_prompt = """You are analyzing a technical note for decisions, conventions, and architectural choices.

Extract each decision as a JSON object:
- "content": The full decision statement (1-2 sentences)
- "rationale": Why this decision was made (null if not stated)
- "confidence": How firm the decision seems (0.0-1.0)
- "type": "decision" | "convention" | "preference"
- "entities": List of technologies/concepts involved

Only extract genuine decisions, not observations or descriptions. A decision implies a choice was made between alternatives.

Return JSON: {"decisions": [...]}"""

        user_prompt = (
            f"Analyze this note for decisions and conventions:\n\n"
            f"Title: {note_title or 'Untitled'}\n\n"
            f"Content:\n{content[:4000]}"
        )

        try:
            response = await self._call_claude(
                system_prompt, user_prompt, max_tokens=1024
            )
            data = self._parse_json_response(response)

            decisions = []
            for item in data.get("decisions", []):
                try:
                    decisions.append(
                        ExtractedDecision(
                            content=item.get("content", ""),
                            rationale=item.get("rationale"),
                            confidence=min(1.0, max(0.0, item.get("confidence", 0.8))),
                            decision_type=item.get("type", "decision"),
                            entities=item.get("entities", []),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse decision: {item}, error: {e}")

            return decisions

        except AIProcessorUnavailableError:
            logger.info("AI processing unavailable, skipping decision extraction")
            return []
        except Exception as e:
            logger.error(f"Error extracting decisions: {e}")
            return []
