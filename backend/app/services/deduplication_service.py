"""Deduplication service: find and analyze duplicate note candidates with caching."""

import asyncio
import logging
from typing import Any

from app.models.search import IndexedNote
from app.services.ai_processor import AIProcessor
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex
from app.services.vault_manager import VaultManager

logger = logging.getLogger(__name__)

# Batch size and delay for rate limiting
DEDUP_BATCH_SIZE = 10
DEDUP_BATCH_DELAY_SECONDS = 1.0


class DeduplicationService:
    """Orchestrates duplicate note discovery and analysis."""

    def __init__(
        self,
        search_index: SearchIndex,
        vault_manager: VaultManager,
        markdown_parser: MarkdownParser,
        ai_processor: AIProcessor,
    ) -> None:
        self.search_index = search_index
        self.vault_manager = vault_manager
        self.markdown_parser = markdown_parser
        self.ai_processor = ai_processor

    async def find_candidates(
        self,
        vault_name: str | None = None,
        limit: int = 50,
    ) -> list[tuple[int, int]]:
        """Find note pairs that might be duplicates (shared tags, not yet suggested)."""
        await self.search_index.initialize()
        return await self.search_index.get_candidate_pairs_for_dedup(
            vault_name=vault_name,
            limit=limit,
        )

    async def analyze_candidates(
        self,
        note_pairs: list[tuple[int, int]] | None = None,
        vault_name: str | None = None,
        limit_pairs: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Run AI deduplication on candidate pairs; store suggestions. Returns (stored_suggestions, pairs_analyzed)."""
        await self.search_index.initialize()

        if note_pairs is None:
            note_pairs = await self.find_candidates(vault_name=vault_name, limit=limit_pairs)

        if not note_pairs:
            return [], 0

        # Flatten to ordered list of unique note IDs (preserve pair order for mapping)
        seen: set[int] = set()
        ordered_note_ids: list[int] = []
        for a, b in note_pairs:
            if a not in seen:
                seen.add(a)
                ordered_note_ids.append(a)
            if b not in seen:
                seen.add(b)
                ordered_note_ids.append(b)

        # Load (ParsedNote, IndexedNote) for each note in order
        notes_tuples: list[tuple[Any, IndexedNote]] = []
        id_to_index: dict[int, int] = {}
        for idx, nid in enumerate(ordered_note_ids):
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
                id_to_index[nid] = len(notes_tuples) - 1
            except Exception as e:
                logger.warning("Failed to load note %s for dedup analysis: %s", nid, e)

        if len(notes_tuples) < 2:
            return [], 0

        # Build id_map: 0-based index -> actual note_id
        index_to_id = ordered_note_ids[: len(notes_tuples)]
        # Only analyze pairs that we have both notes for
        pairs_to_analyze: list[tuple[int, int]] = []
        for a, b in note_pairs:
            if a in id_to_index and b in id_to_index:
                pairs_to_analyze.append((a, b))

        if not pairs_to_analyze:
            return [], 0

        # Run AI in batches; map 0-based note_ids from AI to actual note IDs
        stored: list[dict[str, Any]] = []
        pairs_analyzed = 0

        for offset in range(0, len(pairs_to_analyze), DEDUP_BATCH_SIZE):
            batch_pairs = pairs_to_analyze[offset : offset + DEDUP_BATCH_SIZE]
            if offset > 0:
                await asyncio.sleep(DEDUP_BATCH_DELAY_SECONDS)

            # Unique note IDs in this batch (order preserved)
            batch_note_ids: list[int] = []
            seen_batch: set[int] = set()
            for a, b in batch_pairs:
                for nid in (a, b):
                    if nid in id_to_index and nid not in seen_batch:
                        seen_batch.add(nid)
                        batch_note_ids.append(nid)

            if len(batch_note_ids) < 2:
                continue

            batch_notes = [notes_tuples[id_to_index[nid]] for nid in batch_note_ids]
            result = await self.ai_processor.suggest_deduplication(batch_notes)
            pairs_analyzed += len(batch_pairs)

            for sug in result.suggestions:
                if len(sug.note_ids) < 2:
                    continue
                actual_ids = [
                    batch_note_ids[i] for i in sug.note_ids
                    if 0 <= i < len(batch_note_ids)
                ]
                if len(actual_ids) < 2:
                    continue
                n1, n2 = min(actual_ids), max(actual_ids)
                sid = await self.search_index.store_dedup_suggestion(
                    note_id_1=n1,
                    note_id_2=n2,
                    similarity_score=sug.similarity_score,
                    reasoning=sug.reasoning,
                    suggested_action=sug.suggested_action,
                )
                if sid:
                    row = await self.search_index.get_dedup_suggestion_by_id(sid)
                    if row:
                        stored.append(row)

        return stored, pairs_analyzed
