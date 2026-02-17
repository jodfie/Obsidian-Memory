"""File watcher service for syncing SilverBullet edits to the SQLite index.

Watches /vaults for .md file changes using watchfiles (transitive dep of uvicorn[standard]).
When a file is created/modified, it parses the markdown and indexes via SearchIndex.
When a file is deleted, it removes the note from the index.

The watcher bypasses the HTTP API and rate limiter — it talks to SearchIndex directly.
Double-indexing is avoided via needs_reindex() hash checks.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from watchfiles import awatch, Change

from app.models.search import IndexedNote
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex, compute_file_hash

logger = logging.getLogger(__name__)

# Directories to skip when watching for changes
IGNORED_DIRS = frozenset({
    ".obsidian", ".smart-env", ".stfolder", ".Trash",
    ".backups", ".vscode", ".git",
})


class FileWatcherService:
    """Watches vault directories for .md file changes and syncs to SQLite."""

    def __init__(
        self,
        vault_path: str,
        search_index: SearchIndex,
        parser: MarkdownParser,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.search_index = search_index
        self.parser = parser
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the file watcher in a background task."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("File watcher started for %s", self.vault_path)

    async def stop(self) -> None:
        """Stop the file watcher."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("File watcher stopped")

    async def _watch_loop(self) -> None:
        """Main watch loop with automatic restart on error."""
        while True:
            try:
                async for changes in awatch(
                    self.vault_path,
                    debounce=2000,
                    recursive=True,
                    step=500,
                ):
                    for change_type, path_str in changes:
                        await self._handle_change(change_type, path_str)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("File watcher error, restarting in 5s")
                await asyncio.sleep(5)

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        if path.suffix != ".md":
            return True
        for part in path.parts:
            if part in IGNORED_DIRS:
                return True
        return False

    def _resolve_vault_and_relpath(self, path: Path) -> tuple[str, str] | None:
        """Extract vault name and relative path from an absolute file path.

        Expects: /vaults/<vault_name>/<relative_path>
        Returns: (vault_name, relative_path) or None if path is invalid.
        """
        try:
            rel = path.relative_to(self.vault_path)
        except ValueError:
            return None
        parts = rel.parts
        if len(parts) < 2:
            # File directly in /vaults/ root — no vault name
            return None
        vault_name = parts[0]
        relative_path = str(Path(*parts[1:]))
        return vault_name, relative_path

    async def _handle_change(self, change_type: Change, path_str: str) -> None:
        """Handle a single file change event."""
        path = Path(path_str)

        if self._should_ignore(path):
            return

        resolved = self._resolve_vault_and_relpath(path)
        if not resolved:
            return
        vault_name, relative_path = resolved

        try:
            if change_type == Change.deleted:
                removed = await self.search_index.remove_note(vault_name, relative_path)
                if removed:
                    logger.info("Removed from index: %s/%s", vault_name, relative_path)
            else:
                # Change.added or Change.modified
                await self._index_file(path, vault_name, relative_path)
        except Exception:
            logger.exception(
                "Error handling %s for %s/%s", change_type.name, vault_name, relative_path
            )

    async def _index_file(
        self, path: Path, vault_name: str, relative_path: str
    ) -> None:
        """Parse and index a single .md file."""
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Cannot read %s: %s", path, e)
            return

        file_hash = compute_file_hash(content)

        # Skip if hash matches — avoids double-indexing when the API wrote the file
        if not await self.search_index.needs_reindex(vault_name, relative_path, file_hash):
            return

        stat = path.stat()

        try:
            parsed = self.parser.parse(content)
            created_at = parsed.frontmatter.created or datetime.fromtimestamp(
                stat.st_ctime, tz=timezone.utc
            )
            updated_at = parsed.frontmatter.updated or datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            )
            permalink = parsed.frontmatter.permalink or relative_path

            note = IndexedNote(
                note_id=0,
                vault_name=vault_name,
                relative_path=relative_path,
                permalink=permalink,
                title=parsed.frontmatter.title,
                note_type=(
                    parsed.frontmatter.type.value
                    if hasattr(parsed.frontmatter.type, "value")
                    else str(parsed.frontmatter.type)
                ),
                project=parsed.frontmatter.project,
                content=content,
                tags=parsed.frontmatter.tags,
                wikilinks=parsed.wikilinks,
                relations=parsed.relations,
                observations=parsed.observations,
                created_at=created_at,
                updated_at=updated_at,
                file_hash=file_hash,
            )
        except Exception as e:
            # Parse failed — create a minimal note so the file is still searchable
            logger.warning("Parse error for %s/%s: %s", vault_name, relative_path, e)
            created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
            updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            note = IndexedNote(
                note_id=0,
                vault_name=vault_name,
                relative_path=relative_path,
                permalink=relative_path,
                title=path.stem,
                note_type="note",
                project=None,
                content=content,
                tags=[],
                wikilinks=[],
                relations=[],
                observations=[],
                created_at=created_at,
                updated_at=updated_at,
                file_hash=file_hash,
            )

        await self.search_index.index_note(note)
        logger.info("Indexed: %s/%s", vault_name, relative_path)
