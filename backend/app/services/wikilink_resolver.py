"""Wikilink extraction and resolution service."""

from collections import OrderedDict

from app.models.note import ParsedNote, Wikilink
from app.models.search import IndexedNote
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex


class WikilinkResolutionResult:
    """Result of wikilink resolution."""

    def __init__(
        self,
        wikilink: Wikilink,
        resolved_id: int | None,
        resolution_method: str | None = None,
    ) -> None:
        self.wikilink = wikilink
        self.resolved_id = resolved_id
        self.resolution_method = resolution_method  # 'exact_title', 'permalink', 'case_insensitive', 'path', None


class _LRUCache(OrderedDict):
    """LRU cache with bounded size for permalink resolution."""

    def __init__(self, maxsize: int = 1024, *args: object, **kwargs: object) -> None:
        self.maxsize = maxsize
        super().__init__(*args, **kwargs)

    def __getitem__(self, key: object) -> object:
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key: object, value: object) -> None:
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.maxsize:
            oldest = next(iter(self))
            del self[oldest]


class WikilinkResolver:
    """Service for extracting and resolving wikilinks."""

    def __init__(
        self,
        markdown_parser: MarkdownParser,
        search_index: SearchIndex,
        resolve_cache_maxsize: int = 1024,
    ) -> None:
        """Initialize with dependencies."""
        self.parser = markdown_parser
        self.search_index = search_index
        self._resolve_cache: _LRUCache = _LRUCache(maxsize=resolve_cache_maxsize)

    async def extract_wikilinks(
        self, content: str
    ) -> list[Wikilink]:
        """
        Extract all wikilinks from markdown content.

        Args:
            content: Markdown content

        Returns:
            List of extracted wikilinks
        """
        return self.parser.extract_wikilinks(content)

    def _cache_key(self, target: str, from_vault: str | None) -> tuple[str, str | None]:
        return (target, from_vault)

    async def resolve_wikilink(
        self, wikilink: Wikilink, from_vault: str | None = None
    ) -> WikilinkResolutionResult:
        """
        Resolve a wikilink to a note ID using multiple strategies.

        Resolution order:
        1. Path-based resolution (if path is present)
        2. Exact title match in same vault
        3. Exact permalink match
        4. Exact title match in any vault
        5. Case-insensitive title match

        Uses an LRU cache for frequently-resolved targets.
        """
        if not self.search_index.db:
            await self.search_index.initialize()

        cache_key = self._cache_key(wikilink.target, from_vault)
        if cache_key in self._resolve_cache:
            note_id, method = self._resolve_cache[cache_key]
            return WikilinkResolutionResult(wikilink, note_id, method)

        # Strategy 1: Path-based resolution
        if wikilink.path:
            pass  # Fall through; path-to-note mapping not implemented

        # Strategy 2: Exact title match in same vault
        if from_vault:
            note_id = await self.search_index.resolve_wikilink(
                wikilink.target, from_vault
            )
            if note_id:
                method = "exact_title_same_vault"
                self._resolve_cache[cache_key] = (note_id, method)
                return WikilinkResolutionResult(wikilink, note_id, method)

        # Strategy 3: Exact permalink match
        note_id = await self.search_index.resolve_wikilink(wikilink.target)
        if note_id:
            method = (
                "permalink"
                if wikilink.target.replace("-", "").replace("_", "").islower()
                else "exact_title"
            )
            self._resolve_cache[cache_key] = (note_id, method)
            return WikilinkResolutionResult(wikilink, note_id, method)

        # Strategy 4: Case-insensitive title match handled in resolve_wikilink
        self._resolve_cache[cache_key] = (None, None)
        return WikilinkResolutionResult(wikilink, None, None)

    def _infer_resolution_method(
        self, wikilink: Wikilink, note_id: int | None, from_vault: str | None
    ) -> str | None:
        """Infer resolution method for batch result (best-effort)."""
        if note_id is None:
            return None
        if from_vault:
            return "exact_title_same_vault"
        if wikilink.target.replace("-", "").replace("_", "").islower():
            return "permalink"
        return "exact_title"

    async def resolve_wikilinks(
        self,
        wikilinks: list[Wikilink],
        from_vault: str | None = None,
    ) -> list[WikilinkResolutionResult]:
        """
        Resolve multiple wikilinks in batch via a single batch query.

        Collects unique targets, calls SearchIndex.resolve_batch once, maps
        results back to each wikilink, and updates the LRU cache.
        """
        if not wikilinks:
            return []

        if not self.search_index.db:
            await self.search_index.initialize()

        unique_targets = list(dict.fromkeys(w.target for w in wikilinks))
        batch_map = await self.search_index.resolve_batch(unique_targets, from_vault)

        results: list[WikilinkResolutionResult] = []
        for wikilink in wikilinks:
            note_id = batch_map.get(wikilink.target)
            method = self._infer_resolution_method(wikilink, note_id, from_vault)
            cache_key = self._cache_key(wikilink.target, from_vault)
            self._resolve_cache[cache_key] = (note_id, method)
            results.append(
                WikilinkResolutionResult(wikilink, note_id, method)
            )
        return results

    def clear_resolve_cache(self) -> None:
        """Clear the LRU resolve cache (e.g. after note updates)."""
        self._resolve_cache.clear()

    async def resolve_parsed_note(
        self, parsed_note: ParsedNote, indexed_note: IndexedNote
    ) -> list[WikilinkResolutionResult]:
        """
        Resolve all wikilinks from a parsed note.

        Args:
            parsed_note: Parsed note with wikilinks
            indexed_note: Indexed note with vault information

        Returns:
            List of resolution results
        """
        return await self.resolve_wikilinks(
            parsed_note.wikilinks, indexed_note.vault_name
        )

    async def get_broken_links(
        self,
        parsed_note: ParsedNote,
        indexed_note: IndexedNote,
    ) -> list[Wikilink]:
        """
        Get list of broken (unresolved) wikilinks from a note.

        Args:
            parsed_note: Parsed note with wikilinks
            indexed_note: Indexed note with vault information

        Returns:
            List of broken wikilinks
        """
        results = await self.resolve_parsed_note(parsed_note, indexed_note)
        return [
            result.wikilink
            for result in results
            if result.resolved_id is None
        ]

    async def get_backlinks(
        self, note_id: int
    ) -> list[tuple[int, Wikilink]]:
        """
        Get all notes that link to a given note.

        Args:
            note_id: Target note ID

        Returns:
            List of (source_note_id, wikilink) tuples
        """
        if not self.search_index.db:
            await self.search_index.initialize()

        # Get backlinks from search index
        backlink_results = await self.search_index.get_backlinks(note_id)

        # For each backlink, we'd need to get the actual wikilink objects
        # This is a simplified version - in practice, we'd fetch the parsed notes
        backlinks: list[tuple[int, Wikilink]] = []
        for result in backlink_results:
            # Get the note to extract wikilinks
            indexed_note = await self.search_index.get_note_by_id(
                result.note_id
            )
            if indexed_note:
                # Parse to get wikilinks
                # Note: We'd need the full content, which isn't in IndexedNote
                # This is a limitation - we'd need to fetch from VaultManager
                pass

        return backlinks
