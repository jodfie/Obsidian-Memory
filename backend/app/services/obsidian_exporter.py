"""Obsidian export service for exporting notes from database to .md files.

This module provides the ObsidianExporter class that exports notes from the
Postgres database to Obsidian-compatible .md files with YAML frontmatter.

Usage:
    from app.db import get_db
    from app.services.obsidian_exporter import ObsidianExporter

    async def export_vault(db: AsyncSession, user_id: UUID, output_path: Path):
        exporter = ObsidianExporter(db)
        result = await exporter.export_vault(user_id, output_path)
        return result
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import aiofiles
import frontmatter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import NoteModel
from app.schemas.export import (
    ExportMetadata,
    ExportOptions,
    ExportResult,
    ObsidianSettings,
)
from app.services.exceptions import NoteNotFoundError, UnauthorizedError


class ObsidianExporter:
    """Service for exporting notes from database to Obsidian-compatible .md files.

    This class provides methods for exporting individual notes or entire vaults
    to the filesystem in a format compatible with Obsidian.

    The export process:
    1. Queries notes from the database (optionally filtered by timestamp)
    2. Reconstructs YAML frontmatter from the JSONB column
    3. Writes .md files at the appropriate paths
    4. Creates .obsidian/ config folder with basic settings
    5. Writes .export_metadata.json with export statistics

    Attributes:
        session: SQLAlchemy async session for database operations.
    """

    # Default Obsidian workspace configuration
    DEFAULT_WORKSPACE = {
        "main": {
            "id": "main",
            "type": "split",
            "children": [
                {
                    "id": "file-explorer",
                    "type": "leaf",
                    "state": {
                        "type": "file-explorer",
                        "state": {},
                    },
                }
            ],
            "direction": "vertical",
        },
        "left": {
            "id": "left",
            "type": "split",
            "children": [],
            "direction": "horizontal",
            "width": 300,
        },
        "right": {
            "id": "right",
            "type": "split",
            "children": [],
            "direction": "horizontal",
            "width": 300,
        },
        "active": "main",
        "lastOpenFiles": [],
    }

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            session: SQLAlchemy AsyncSession instance.
        """
        self._session = session

    async def export_vault(
        self,
        user_id: UUID,
        output_path: Path,
        since: datetime | None = None,
        options: ExportOptions | None = None,
    ) -> ExportResult:
        """Export all notes for a user to the filesystem.

        This method exports notes as .md files, creating the directory structure
        based on the note paths. It also creates the .obsidian/ config folder
        and .export_metadata.json file.

        Args:
            user_id: UUID of the user whose notes to export.
            output_path: Root directory for the exported vault.
            since: Only export notes modified since this timestamp (optional).
                If provided, performs an incremental export.
            options: Export options (overwrite, include_metadata, etc.).

        Returns:
            ExportResult with counts and any errors encountered.

        Raises:
            OSError: If unable to create directories or write files.
        """
        if options is None:
            options = ExportOptions(since=since)
        elif since is not None:
            options.since = since

        result = ExportResult()

        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)

        # Create .obsidian config folder
        await self._create_obsidian_config(output_path)

        # Query notes for this user
        stmt = select(NoteModel).where(NoteModel.user_id == str(user_id))

        if options.since is not None:
            stmt = stmt.where(NoteModel.updated_at >= options.since)

        stmt = stmt.order_by(NoteModel.path)

        db_result = await self._session.execute(stmt)
        notes = db_result.scalars().all()

        # Export each note
        for note in notes:
            try:
                file_path = output_path / note.path

                # Check if file exists and handle overwrite option
                if file_path.exists() and not options.overwrite:
                    result.skipped_count += 1
                    continue

                # Export the note
                size = await self._write_note_file(note, file_path)
                result.success_count += 1
                result.total_size_bytes += size
                result.exported_paths.append(note.path)

            except Exception as e:
                result.error_count += 1
                result.errors.append(f"Failed to export {note.path}: {str(e)}")

        # Write export metadata
        if options.include_metadata:
            await self._write_export_metadata(
                output_path=output_path,
                user_id=user_id,
                result=result,
                since=options.since,
            )

        return result

    async def export_note(
        self,
        note_id: UUID,
        user_id: UUID,
        output_path: Path,
    ) -> Path:
        """Export a single note to the filesystem.

        Args:
            note_id: UUID of the note to export.
            user_id: UUID of the requesting user (for authorization).
            output_path: Root directory for the exported vault.

        Returns:
            Path to the exported file.

        Raises:
            NoteNotFoundError: If no note exists with the given ID.
            UnauthorizedError: If the note exists but belongs to a different user.
            OSError: If unable to create directories or write the file.
        """
        # Fetch the note
        stmt = select(NoteModel).where(NoteModel.id == str(note_id))
        db_result = await self._session.execute(stmt)
        note = db_result.scalar_one_or_none()

        if note is None:
            raise NoteNotFoundError(str(note_id), by_field="id")

        # Check user ownership
        if note.user_id != str(user_id):
            raise UnauthorizedError(str(note_id), str(user_id))

        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)

        # Write the note file
        file_path = output_path / note.path
        await self._write_note_file(note, file_path)

        return file_path

    async def _write_note_file(self, note: NoteModel, file_path: Path) -> int:
        """Write a single note to a .md file with YAML frontmatter.

        Args:
            note: NoteModel instance to export.
            file_path: Full path where the file should be written.

        Returns:
            Size of the written file in bytes.

        Raises:
            OSError: If unable to create directories or write the file.
        """
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Build frontmatter dict
        fm_dict = self._build_frontmatter(note)

        # Create Post object with frontmatter and content
        post = frontmatter.Post(content=note.content)
        post.metadata = fm_dict

        # Serialize to string
        content = frontmatter.dumps(post)

        # Write file
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        return len(content.encode("utf-8"))

    def _build_frontmatter(self, note: NoteModel) -> dict[str, Any]:
        """Build the YAML frontmatter dictionary for a note.

        Combines the stored frontmatter JSONB with standard metadata fields.

        Args:
            note: NoteModel instance.

        Returns:
            Dictionary to be serialized as YAML frontmatter.
        """
        # Start with stored frontmatter
        fm_dict: dict[str, Any] = dict(note.frontmatter) if note.frontmatter else {}

        # Add/update standard fields
        # Title is always included
        fm_dict["title"] = note.title

        # Add timestamps in ISO format
        if note.created_at:
            fm_dict["created"] = note.created_at.isoformat()
        if note.updated_at:
            fm_dict["updated"] = note.updated_at.isoformat()

        # Add note ID for reference
        fm_dict["id"] = note.id

        return fm_dict

    async def _create_obsidian_config(self, output_path: Path) -> None:
        """Create .obsidian/ config folder with basic settings.

        Creates the .obsidian directory if it doesn't exist and writes
        basic configuration files needed for Obsidian to recognize the
        folder as a vault.

        Args:
            output_path: Root directory of the vault.
        """
        obsidian_dir = output_path / ".obsidian"

        # Only create if doesn't exist
        if obsidian_dir.exists():
            return

        obsidian_dir.mkdir(parents=True, exist_ok=True)

        # Write app.json with basic settings
        settings = ObsidianSettings()
        app_json_path = obsidian_dir / "app.json"
        async with aiofiles.open(app_json_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(settings.model_dump_obsidian(), indent=2))

        # Write appearance.json
        appearance = {
            "baseFontSize": 16,
            "interfaceFontFamily": "",
            "textFontFamily": "",
            "monospaceFontFamily": "",
            "theme": "obsidian",
        }
        appearance_path = obsidian_dir / "appearance.json"
        async with aiofiles.open(appearance_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(appearance, indent=2))

        # Write workspace.json
        workspace_path = obsidian_dir / "workspace.json"
        async with aiofiles.open(workspace_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(self.DEFAULT_WORKSPACE, indent=2))

        # Write core-plugins.json (enable essential plugins)
        core_plugins = [
            "file-explorer",
            "global-search",
            "switcher",
            "graph",
            "backlink",
            "outgoing-link",
            "tag-pane",
            "page-preview",
            "starred",
            "markdown-importer",
            "word-count",
            "command-palette",
            "editor-status",
        ]
        plugins_path = obsidian_dir / "core-plugins.json"
        async with aiofiles.open(plugins_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(core_plugins, indent=2))

        # Write hotkeys.json (empty)
        hotkeys_path = obsidian_dir / "hotkeys.json"
        async with aiofiles.open(hotkeys_path, "w", encoding="utf-8") as f:
            await f.write("{}")

    async def _write_export_metadata(
        self,
        output_path: Path,
        user_id: UUID,
        result: ExportResult,
        since: datetime | None = None,
    ) -> None:
        """Write .export_metadata.json with export statistics.

        Args:
            output_path: Root directory of the exported vault.
            user_id: User ID whose notes were exported.
            result: ExportResult with counts and statistics.
            since: If incremental export, the since timestamp used.
        """
        metadata = ExportMetadata(
            exported_at=datetime.now(timezone.utc),
            note_count=result.success_count,
            total_size_bytes=result.total_size_bytes,
            user_id=str(user_id),
            incremental_since=since,
        )

        metadata_path = output_path / ".export_metadata.json"
        async with aiofiles.open(metadata_path, "w", encoding="utf-8") as f:
            await f.write(metadata.model_dump_json(indent=2))
