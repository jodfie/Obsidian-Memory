"""Profile synthesis frequency tracker.

Tracks per-project write counts and triggers background profile synthesis
when the configured threshold is reached.
"""

import asyncio
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class ProfileSynthesisTracker:
    """Tracks write counts per project and triggers profile synthesis.

    Uses in-memory counters (reset on restart). Each project has an
    independent counter and lock to prevent duplicate synthesis runs.
    """

    def __init__(self, frequency: int | None = None) -> None:
        self.frequency = frequency or settings.profile_synthesis_frequency
        self.enabled = settings.profile_synthesis_enabled
        self._write_counts: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._synthesis_in_progress: set[str] = set()

    def _get_lock(self, project: str) -> asyncio.Lock:
        """Get or create a lock for the given project."""
        if project not in self._locks:
            self._locks[project] = asyncio.Lock()
        return self._locks[project]

    def get_write_count(self, project: str) -> int:
        """Get current write count for a project."""
        return self._write_counts.get(project, 0)

    def reset_count(self, project: str) -> None:
        """Reset write count for a project."""
        self._write_counts[project] = 0

    async def record_write(
        self,
        project: str | None,
        search_index: Any,
        ai_processor: Any,
    ) -> bool:
        """Record a note write and trigger synthesis if threshold reached.

        Args:
            project: Project identifier (None = no tracking)
            search_index: SearchIndex for querying notes
            ai_processor: AIProcessor for synthesis

        Returns:
            True if synthesis was triggered, False otherwise
        """
        if not self.enabled or not project:
            return False

        self._write_counts[project] = self._write_counts.get(project, 0) + 1
        count = self._write_counts[project]

        logger.debug(f"Project '{project}' write count: {count}/{self.frequency}")

        if count >= self.frequency:
            return await self._maybe_synthesize(project, search_index, ai_processor)

        return False

    async def _maybe_synthesize(
        self,
        project: str,
        search_index: Any,
        ai_processor: Any,
    ) -> bool:
        """Attempt to trigger synthesis, with lock to prevent duplicates."""
        lock = self._get_lock(project)

        if project in self._synthesis_in_progress:
            logger.debug(f"Synthesis already in progress for '{project}', skipping")
            return False

        async with lock:
            # Double-check after acquiring lock
            if project in self._synthesis_in_progress:
                return False

            # Check count again (may have been reset by another task)
            if self._write_counts.get(project, 0) < self.frequency:
                return False

            self._synthesis_in_progress.add(project)
            try:
                logger.info(f"Triggering profile synthesis for project '{project}'")
                await self._run_synthesis(project, search_index, ai_processor)
                self._write_counts[project] = 0
                return True
            except Exception as e:
                logger.error(f"Profile synthesis failed for '{project}': {e}")
                return False
            finally:
                self._synthesis_in_progress.discard(project)

    async def _run_synthesis(
        self,
        project: str,
        search_index: Any,
        ai_processor: Any,
    ) -> None:
        """Run the actual synthesis and store the profile note."""
        profile = await ai_processor.synthesize_profile(project, search_index)
        logger.info(
            f"Profile synthesized for '{project}': "
            f"{len(profile.static_facts)} facts, "
            f"{len(profile.dynamic_patterns)} patterns, "
            f"{len(profile.key_entities)} entity categories"
        )
        # Profile storage is handled by the API layer (Task 35.4)
        # For now, just log the result
