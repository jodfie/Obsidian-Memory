"""Pattern detection service: cross-session/cross-note analysis with caching."""

import hashlib
import logging
from typing import Any

from app.models.search import IndexedNote
from app.services.ai_processor import AIProcessor
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex
from app.services.session_manager import SessionManager
from app.services.vault_manager import VaultManager

logger = logging.getLogger(__name__)


class PatternDetectionService:
    """Orchestrates pattern detection across notes and sessions with content-hash caching."""

    def __init__(
        self,
        search_index: SearchIndex,
        vault_manager: VaultManager,
        markdown_parser: MarkdownParser,
        ai_processor: AIProcessor,
        session_manager: SessionManager,
    ) -> None:
        self.search_index = search_index
        self.vault_manager = vault_manager
        self.markdown_parser = markdown_parser
        self.ai_processor = ai_processor
        self.session_manager = session_manager

    def _content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content for cache key."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    async def analyze_patterns(
        self,
        note_ids: list[int] | None = None,
        session_ids: list[str] | None = None,
        limit_notes: int = 50,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Run pattern detection on notes and optional session summaries.

        Combines note content and session summary text, then either returns
        cached patterns (same content hash) or runs AI and stores new patterns.

        Args:
            note_ids: Optional list of note IDs to analyze (None = use recent notes)
            session_ids: Optional list of session IDs whose summaries to include
            limit_notes: Max notes to include when note_ids is None

        Returns:
            (list of pattern dicts, from_cache)
        """
        await self.search_index.initialize()

        # Build ordered list of note IDs to analyze
        if note_ids:
            ordered_note_ids = note_ids[:limit_notes]
        else:
            from app.models.search import SearchQuery, SortOrder
            query = SearchQuery(query="", limit=limit_notes, sort=SortOrder.UPDATED_DESC)
            results = await self.search_index.search(query)
            ordered_note_ids = [r.note_id for r in results.results]

        # Load note content and build (ParsedNote, IndexedNote) tuples; track note IDs in order
        notes_tuples: list[tuple[Any, IndexedNote]] = []
        note_ids_used: list[int] = []
        content_parts: list[str] = []

        for nid in ordered_note_ids:
            try:
                note = await self.search_index.get_note_by_id(nid)
                if not note:
                    continue
                vault_file = await self.vault_manager.read_file(
                    note.relative_path, vault=note.vault_name
                )
                parsed = self.markdown_parser.parse(vault_file.content)
                indexed_note = note.model_copy(update={"content": vault_file.content})
                notes_tuples.append((parsed, indexed_note))
                note_ids_used.append(nid)
                content_parts.append(f"[Note {nid}] {parsed.frontmatter.title}\n{parsed.raw_content[:800]}\n")
            except Exception as e:
                logger.warning("Failed to load note %s for pattern analysis: %s", nid, e)
                continue

        # Append session summaries
        if session_ids:
            for sid in session_ids:
                try:
                    session = await self.session_manager.get_session(sid)
                    if session and session.summary:
                        summary_text = (
                            session.summary.get("summary_text", "")
                            if isinstance(session.summary, dict)
                            else str(session.summary)
                        )
                        content_parts.append(f"[Session {sid}]\n{summary_text[:1000]}\n")
                except Exception as e:
                    logger.warning("Failed to load session %s for pattern analysis: %s", sid, e)

        if not notes_tuples:
            return [], False

        combined = "\n".join(content_parts)
        content_hash = self._content_hash(combined)

        # Cache lookup
        existing_run_id = await self.search_index.get_pattern_run_by_content_hash(content_hash)
        if existing_run_id is not None:
            patterns = await self.search_index.get_patterns(run_id=existing_run_id)
            return patterns, True

        # Run AI detection
        result = await self.ai_processor.detect_patterns(notes_tuples)
        run_id = await self.search_index.create_pattern_run(content_hash)

        # Map 0-based note_ids from AI to actual note IDs (same order as notes_tuples)
        id_map = note_ids_used

        for p in result.patterns:
            actual_note_ids = [
                id_map[i] for i in p.note_ids
                if 0 <= i < len(id_map)
            ]
            if not actual_note_ids:
                continue
            await self.search_index.store_pattern(
                run_id=run_id,
                pattern_name=p.pattern_name,
                description=p.description,
                category=p.category,
                confidence=p.confidence,
                frequency=p.frequency,
                note_ids=actual_note_ids,
            )

        patterns = await self.search_index.get_patterns(run_id=run_id)
        return patterns, False
