"""Pydantic schemas for Obsidian export operations.

These schemas define the request/response models for exporting notes
from the database to .md files compatible with Obsidian.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExportOptions(BaseModel):
    """Options for controlling the export behavior.

    Attributes:
        since: Only export notes modified since this timestamp (incremental export).
            If None, export all notes.
        overwrite: Whether to overwrite existing files. If False, skip files that exist.
        include_metadata: Whether to write .export_metadata.json with export stats.
    """

    since: datetime | None = Field(
        default=None,
        description="Only export notes modified since this timestamp (incremental export)",
    )
    overwrite: bool = Field(
        default=True,
        description="Whether to overwrite existing files",
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to write .export_metadata.json with export stats",
    )


class ExportResult(BaseModel):
    """Result of an export operation.

    Attributes:
        success_count: Number of notes successfully exported.
        error_count: Number of notes that failed to export.
        skipped_count: Number of notes skipped (e.g., already exists and overwrite=False).
        total_size_bytes: Total size of all exported files in bytes.
        errors: List of error messages for failed exports.
        exported_paths: List of paths that were successfully exported.
    """

    success_count: int = Field(
        default=0,
        description="Number of notes successfully exported",
    )
    error_count: int = Field(
        default=0,
        description="Number of notes that failed to export",
    )
    skipped_count: int = Field(
        default=0,
        description="Number of notes skipped (already exists, overwrite=False)",
    )
    total_size_bytes: int = Field(
        default=0,
        description="Total size of all exported files in bytes",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages for failed exports",
    )
    exported_paths: list[str] = Field(
        default_factory=list,
        description="List of paths that were successfully exported",
    )


class ExportMetadata(BaseModel):
    """Metadata written to .export_metadata.json in the export directory.

    Attributes:
        exported_at: Timestamp when the export completed.
        note_count: Total number of notes exported.
        total_size_bytes: Total size of all exported files.
        user_id: User ID whose notes were exported.
        incremental_since: If incremental export, the since timestamp used.
        vault_name: Name of the vault (used for .obsidian config).
    """

    exported_at: datetime = Field(
        ...,
        description="Timestamp when the export completed",
    )
    note_count: int = Field(
        ...,
        description="Total number of notes exported",
    )
    total_size_bytes: int = Field(
        ...,
        description="Total size of all exported files",
    )
    user_id: str = Field(
        ...,
        description="User ID whose notes were exported",
    )
    incremental_since: datetime | None = Field(
        default=None,
        description="If incremental export, the since timestamp used",
    )
    vault_name: str = Field(
        default="Obsidian-Memory",
        description="Name of the vault",
    )


class ObsidianSettings(BaseModel):
    """Basic Obsidian vault settings written to .obsidian/app.json.

    These are minimal settings to make the exported vault functional in Obsidian.
    """

    showLineNumber: bool = Field(default=True)
    readableLineLength: bool = Field(default=True)
    strictLineBreaks: bool = Field(default=False)
    vimMode: bool = Field(default=False)
    spellcheck: bool = Field(default=True)
    defaultViewMode: str = Field(default="source")
    livePreview: bool = Field(default=True)
    foldHeading: bool = Field(default=True)
    foldIndent: bool = Field(default=True)
    showFrontmatter: bool = Field(default=True)

    def model_dump_obsidian(self) -> dict[str, Any]:
        """Dump settings in Obsidian's expected format (camelCase keys)."""
        return self.model_dump()
