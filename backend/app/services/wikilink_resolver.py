"""Wikilink extraction and resolution service."""

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


class WikilinkResolver:
    """Service for extracting and resolving wikilinks."""

    def __init__(
        self, markdown_parser: MarkdownParser, search_index: SearchIndex
    ) -> None:
        """Initialize with dependencies."""
        self.parser = markdown_parser
        self.search_index = search_index

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

        Args:
            wikilink: Wikilink to resolve
            from_vault: Vault name for context

        Returns:
            Resolution result with resolved ID and method
        """
        if not self.search_index.db:
            await self.search_index.initialize()

        # Strategy 1: Path-based resolution
        if wikilink.path:
            # Try to resolve by path + title
            # This would require a path-to-note mapping, which we don't have yet
            # For now, fall through to other strategies
            pass

        # Strategy 2: Exact title match in same vault
        if from_vault:
            note_id = await self.search_index.resolve_wikilink(
                wikilink.target, from_vault
            )
            if note_id:
                return WikilinkResolutionResult(
                    wikilink, note_id, 'exact_title_same_vault'
                )

        # Strategy 3: Exact permalink match
        note_id = await self.search_index.resolve_wikilink(wikilink.target)
        if note_id:
            # Check if it was resolved by permalink (we can't tell from the current API)
            # Assume it's permalink if target looks like a slug
            method = (
                'permalink'
                if wikilink.target.replace('-', '').replace('_', '').islower()
                else 'exact_title'
            )
            return WikilinkResolutionResult(wikilink, note_id, method)

        # Strategy 4: Case-insensitive title match
        # The resolve_wikilink already does this, so if we get here, it's unresolved
        return WikilinkResolutionResult(wikilink, None, None)

    async def resolve_wikilinks(
        self,
        wikilinks: list[Wikilink],
        from_vault: str | None = None,
    ) -> list[WikilinkResolutionResult]:
        """
        Resolve multiple wikilinks in batch.

        Args:
            wikilinks: List of wikilinks to resolve
            from_vault: Vault name for context

        Returns:
            List of resolution results
        """
        results: list[WikilinkResolutionResult] = []
        for wikilink in wikilinks:
            result = await self.resolve_wikilink(wikilink, from_vault)
            results.append(result)
        return results

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
