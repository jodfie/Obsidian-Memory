#!/usr/bin/env python3
"""
Supabase Migration Script for Obsidian-Memory

Migrates existing .md files and SQLite data to Supabase Postgres.

Requirements (install with pip):
    - supabase>=2.0.0
    - python-frontmatter>=1.0.0
    - python-dotenv>=1.0.0

Usage:
    python migrate_to_supabase.py --vault-path /path/to/vault
    python migrate_to_supabase.py --vault-path /path/to/vault --dry-run
    python migrate_to_supabase.py --vault-path /path/to/vault --sqlite-db /path/to/sessions.db

Environment Variables (or .env file):
    SUPABASE_URL - Supabase project URL
    SUPABASE_KEY - Supabase service role key (required for migration)
    MIGRATION_USER_ID - UUID of the user to assign notes to
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter
from dotenv import load_dotenv
from supabase import Client, create_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================


@dataclass
class Note:
    """Represents a note to be migrated."""

    path: str
    title: str
    content: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    wikilinks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Relation:
    """Represents a relation between notes."""

    source_path: str
    target_path: str
    relation_type: str  # 'wikilink', 'tag', 'observation', 'embed', 'reference'
    context: str | None = None


@dataclass
class Session:
    """Represents a Claude Code session."""

    project: str | None
    started_at: datetime
    ended_at: datetime | None
    summary: str | None
    events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MigrationStats:
    """Tracks migration statistics."""

    total_files: int = 0
    processed_files: int = 0
    successful_notes: int = 0
    failed_notes: int = 0
    total_relations: int = 0
    successful_relations: int = 0
    failed_relations: int = 0
    total_sessions: int = 0
    successful_sessions: int = 0
    failed_sessions: int = 0
    errors: list[str] = field(default_factory=list)


# ==============================================================================
# Parsing Functions
# ==============================================================================


def extract_wikilinks(content: str) -> list[tuple[str, str]]:
    """
    Extract wikilinks from markdown content.

    Returns list of (link_target, context) tuples.
    """
    # Match [[link]] or [[link|display text]]
    pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
    matches = []

    for match in re.finditer(pattern, content):
        link_target = match.group(1).strip()
        # Get surrounding context (up to 100 chars before and after)
        start = max(0, match.start() - 100)
        end = min(len(content), match.end() + 100)
        context = content[start:end].strip()
        # Clean up context - remove extra whitespace
        context = " ".join(context.split())
        matches.append((link_target, context))

    return matches


def extract_tags(content: str) -> list[tuple[str, str]]:
    """
    Extract #tags from markdown content.

    Returns list of (tag, context) tuples.
    Excludes tags in code blocks and URLs.
    """
    # Remove code blocks first to avoid matching tags in code
    code_block_pattern = r"```[\s\S]*?```|`[^`]+`"
    clean_content = re.sub(code_block_pattern, "", content)

    # Match #tag (but not ##heading or #123 or URLs with #)
    # Tags must start with a letter and can contain letters, numbers, underscores, hyphens
    pattern = r"(?<![/\w])#([a-zA-Z][a-zA-Z0-9_-]*)"
    matches = []

    for match in re.finditer(pattern, clean_content):
        tag = match.group(1)
        # Skip if it looks like a heading (preceded by newline and another #)
        pos = match.start()
        if pos > 0 and clean_content[pos - 1] == "#":
            continue

        # Get surrounding context
        start = max(0, match.start() - 100)
        end = min(len(clean_content), match.end() + 100)
        context = clean_content[start:end].strip()
        context = " ".join(context.split())
        matches.append((tag, context))

    return matches


def parse_markdown_file(file_path: Path, vault_path: Path) -> Note | None:
    """
    Parse a markdown file and extract note data.

    Args:
        file_path: Path to the markdown file
        vault_path: Root vault path for relative path calculation

    Returns:
        Note object or None if parsing fails
    """
    try:
        # Read and parse frontmatter
        post = frontmatter.load(file_path)

        # Calculate relative path from vault
        relative_path = str(file_path.relative_to(vault_path))

        # Extract title from frontmatter or filename
        title = post.metadata.get("title") or post.metadata.get("name")
        if not title:
            title = file_path.stem  # Filename without extension

        # Get file timestamps
        stat = file_path.stat()
        created_at = datetime.fromtimestamp(stat.st_ctime)
        updated_at = datetime.fromtimestamp(stat.st_mtime)

        # Override with frontmatter dates if present
        if "created" in post.metadata:
            try:
                created_at = datetime.fromisoformat(str(post.metadata["created"]))
            except (ValueError, TypeError):
                pass
        if "updated" in post.metadata or "modified" in post.metadata:
            try:
                date_str = str(post.metadata.get("updated") or post.metadata.get("modified"))
                updated_at = datetime.fromisoformat(date_str)
            except (ValueError, TypeError):
                pass

        # Extract wikilinks and tags from content
        wikilinks = [link for link, _ in extract_wikilinks(post.content)]
        tags = [tag for tag, _ in extract_tags(post.content)]

        # Also check frontmatter for tags
        if "tags" in post.metadata:
            fm_tags = post.metadata["tags"]
            if isinstance(fm_tags, list):
                tags.extend(fm_tags)
            elif isinstance(fm_tags, str):
                # Handle comma-separated or space-separated tags
                tags.extend(re.split(r"[,\s]+", fm_tags))

        # Deduplicate tags
        tags = list(set(tags))

        return Note(
            path=relative_path,
            title=title,
            content=post.content,
            frontmatter=dict(post.metadata),
            wikilinks=wikilinks,
            tags=tags,
            created_at=created_at,
            updated_at=updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to parse {file_path}: {e}")
        return None


def extract_relations(note: Note) -> list[Relation]:
    """
    Extract all relations from a note.

    Returns list of Relation objects for wikilinks and tags.
    """
    relations = []

    # Read the content again for context extraction
    wikilink_matches = extract_wikilinks(note.content)
    tag_matches = extract_tags(note.content)

    # Add wikilink relations
    for link_target, context in wikilink_matches:
        # Normalize link target to path
        target_path = link_target
        if not target_path.endswith(".md"):
            target_path = f"{target_path}.md"

        relations.append(
            Relation(
                source_path=note.path,
                target_path=target_path,
                relation_type="wikilink",
                context=context[:500] if context else None,  # Limit context length
            )
        )

    # Add tag relations
    for tag, context in tag_matches:
        relations.append(
            Relation(
                source_path=note.path,
                target_path=f"#/{tag}",  # Tags use #/ prefix as pseudo-path
                relation_type="tag",
                context=context[:500] if context else None,
            )
        )

    return relations


# ==============================================================================
# SQLite Session Loading
# ==============================================================================


def load_sqlite_sessions(db_path: Path) -> list[Session]:
    """
    Load sessions from existing SQLite database.

    Attempts to handle various schema formats.
    """
    sessions = []

    if not db_path.exists():
        logger.warning(f"SQLite database not found: {db_path}")
        return sessions

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Try to get table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found tables in SQLite: {tables}")

        # Look for sessions table
        if "sessions" in tables:
            cursor.execute("PRAGMA table_info(sessions)")
            columns = [row[1] for row in cursor.fetchall()]
            logger.info(f"Sessions table columns: {columns}")

            # Build query based on available columns
            cursor.execute("SELECT * FROM sessions")

            for row in cursor.fetchall():
                row_dict = dict(row)

                # Parse dates
                started_at = datetime.now()
                ended_at = None
                if "started_at" in row_dict and row_dict["started_at"]:
                    try:
                        started_at = datetime.fromisoformat(row_dict["started_at"])
                    except (ValueError, TypeError):
                        pass
                if "ended_at" in row_dict and row_dict["ended_at"]:
                    try:
                        ended_at = datetime.fromisoformat(row_dict["ended_at"])
                    except (ValueError, TypeError):
                        pass

                # Parse events
                events = []
                if "events" in row_dict and row_dict["events"]:
                    try:
                        events = json.loads(row_dict["events"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                sessions.append(
                    Session(
                        project=row_dict.get("project"),
                        started_at=started_at,
                        ended_at=ended_at,
                        summary=row_dict.get("summary"),
                        events=events,
                    )
                )

        conn.close()
        logger.info(f"Loaded {len(sessions)} sessions from SQLite")

    except Exception as e:
        logger.error(f"Failed to load SQLite sessions: {e}")

    return sessions


# ==============================================================================
# Supabase Migration
# ==============================================================================


class SupabaseMigrator:
    """Handles migration to Supabase."""

    def __init__(self, supabase_url: str, supabase_key: str, user_id: str, dry_run: bool = False):
        self.dry_run = dry_run
        self.user_id = user_id

        if not dry_run:
            self.client: Client = create_client(supabase_url, supabase_key)
        else:
            self.client = None

        # Cache for note IDs (path -> uuid)
        self.note_ids: dict[str, str] = {}

    def migrate_notes(self, notes: list[Note], stats: MigrationStats) -> None:
        """Migrate notes to Supabase in batches."""
        batch_size = 50
        total = len(notes)

        logger.info(f"Migrating {total} notes to Supabase...")

        for i in range(0, total, batch_size):
            batch = notes[i : i + batch_size]
            batch_records = []

            for note in batch:
                # Generate UUID for this note
                note_id = str(uuid.uuid4())
                self.note_ids[note.path] = note_id

                record = {
                    "id": note_id,
                    "path": note.path,
                    "title": note.title,
                    "content": note.content,
                    "frontmatter": note.frontmatter,
                    "user_id": self.user_id,
                }

                # Add timestamps if available
                if note.created_at:
                    record["created_at"] = note.created_at.isoformat()
                if note.updated_at:
                    record["updated_at"] = note.updated_at.isoformat()

                batch_records.append(record)
                stats.processed_files += 1

            if self.dry_run:
                logger.info(f"[DRY RUN] Would insert {len(batch_records)} notes")
                stats.successful_notes += len(batch_records)
            else:
                try:
                    response = self.client.table("notes").upsert(
                        batch_records, on_conflict="path"
                    ).execute()
                    stats.successful_notes += len(batch_records)
                    logger.info(f"Inserted batch: {i + 1}-{min(i + batch_size, total)}/{total} notes")
                except Exception as e:
                    stats.failed_notes += len(batch_records)
                    stats.errors.append(f"Failed to insert notes batch {i}: {e}")
                    logger.error(f"Failed to insert notes batch: {e}")

        logger.info(f"Notes migration complete: {stats.successful_notes} successful, {stats.failed_notes} failed")

    def migrate_relations(self, relations: list[Relation], stats: MigrationStats) -> None:
        """Migrate relations to Supabase in batches."""
        batch_size = 100
        total = len(relations)
        stats.total_relations = total

        logger.info(f"Migrating {total} relations to Supabase...")

        for i in range(0, total, batch_size):
            batch = relations[i : i + batch_size]
            batch_records = []

            for rel in batch:
                # Get source note ID
                source_id = self.note_ids.get(rel.source_path)
                if not source_id:
                    logger.warning(f"Source note not found for relation: {rel.source_path}")
                    stats.failed_relations += 1
                    continue

                record = {
                    "id": str(uuid.uuid4()),
                    "source_id": source_id,
                    "target_path": rel.target_path,
                    "relation_type": rel.relation_type,
                    "context": rel.context,
                }
                batch_records.append(record)

            if not batch_records:
                continue

            if self.dry_run:
                logger.info(f"[DRY RUN] Would insert {len(batch_records)} relations")
                stats.successful_relations += len(batch_records)
            else:
                try:
                    response = self.client.table("relations").insert(batch_records).execute()
                    stats.successful_relations += len(batch_records)
                    logger.info(
                        f"Inserted batch: {i + 1}-{min(i + batch_size, total)}/{total} relations"
                    )
                except Exception as e:
                    stats.failed_relations += len(batch_records)
                    stats.errors.append(f"Failed to insert relations batch {i}: {e}")
                    logger.error(f"Failed to insert relations batch: {e}")

        logger.info(
            f"Relations migration complete: {stats.successful_relations} successful, {stats.failed_relations} failed"
        )

    def migrate_sessions(self, sessions: list[Session], stats: MigrationStats) -> None:
        """Migrate sessions to Supabase."""
        stats.total_sessions = len(sessions)

        if not sessions:
            logger.info("No sessions to migrate")
            return

        logger.info(f"Migrating {len(sessions)} sessions to Supabase...")

        batch_size = 50
        total = len(sessions)

        for i in range(0, total, batch_size):
            batch = sessions[i : i + batch_size]
            batch_records = []

            for session in batch:
                record = {
                    "id": str(uuid.uuid4()),
                    "project": session.project,
                    "started_at": session.started_at.isoformat(),
                    "summary": session.summary,
                    "events": session.events,
                    "user_id": self.user_id,
                }

                if session.ended_at:
                    record["ended_at"] = session.ended_at.isoformat()

                batch_records.append(record)

            if self.dry_run:
                logger.info(f"[DRY RUN] Would insert {len(batch_records)} sessions")
                stats.successful_sessions += len(batch_records)
            else:
                try:
                    response = self.client.table("sessions").insert(batch_records).execute()
                    stats.successful_sessions += len(batch_records)
                    logger.info(
                        f"Inserted batch: {i + 1}-{min(i + batch_size, total)}/{total} sessions"
                    )
                except Exception as e:
                    stats.failed_sessions += len(batch_records)
                    stats.errors.append(f"Failed to insert sessions batch {i}: {e}")
                    logger.error(f"Failed to insert sessions batch: {e}")

        logger.info(
            f"Sessions migration complete: {stats.successful_sessions} successful, {stats.failed_sessions} failed"
        )


# ==============================================================================
# Main Migration Logic
# ==============================================================================


def find_markdown_files(vault_path: Path, exclude_patterns: list[str] | None = None) -> list[Path]:
    """
    Recursively find all .md files in the vault.

    Args:
        vault_path: Root path to search
        exclude_patterns: List of patterns to exclude (e.g., 'node_modules', '.git')

    Returns:
        List of Path objects for markdown files
    """
    if exclude_patterns is None:
        exclude_patterns = [
            "node_modules",
            ".git",
            ".obsidian",
            ".trash",
            "__pycache__",
            ".venv",
            "venv",
        ]

    files = []

    for md_file in vault_path.rglob("*.md"):
        # Check if any excluded pattern is in the path
        path_str = str(md_file)
        if any(pattern in path_str for pattern in exclude_patterns):
            continue
        files.append(md_file)

    return sorted(files)


def run_migration(
    vault_path: Path,
    supabase_url: str,
    supabase_key: str,
    user_id: str,
    sqlite_db: Path | None = None,
    dry_run: bool = False,
    exclude_patterns: list[str] | None = None,
) -> MigrationStats:
    """
    Run the full migration process.

    Args:
        vault_path: Path to the Obsidian vault
        supabase_url: Supabase project URL
        supabase_key: Supabase service role key
        user_id: UUID of user to assign notes to
        sqlite_db: Optional path to SQLite database with sessions
        dry_run: If True, don't actually insert data
        exclude_patterns: Patterns to exclude from migration

    Returns:
        MigrationStats with results
    """
    stats = MigrationStats()

    # Find all markdown files
    logger.info(f"Scanning vault: {vault_path}")
    md_files = find_markdown_files(vault_path, exclude_patterns)
    stats.total_files = len(md_files)
    logger.info(f"Found {stats.total_files} markdown files")

    if stats.total_files == 0:
        logger.warning("No markdown files found!")
        return stats

    # Parse all files
    logger.info("Parsing markdown files...")
    notes: list[Note] = []
    all_relations: list[Relation] = []

    for i, file_path in enumerate(md_files, 1):
        note = parse_markdown_file(file_path, vault_path)
        if note:
            notes.append(note)
            all_relations.extend(extract_relations(note))

        if i % 100 == 0:
            logger.info(f"Parsed {i}/{stats.total_files} files...")

    logger.info(f"Successfully parsed {len(notes)} notes with {len(all_relations)} relations")

    # Load SQLite sessions if provided
    sessions: list[Session] = []
    if sqlite_db:
        sessions = load_sqlite_sessions(sqlite_db)

    # Create migrator and run migration
    migrator = SupabaseMigrator(supabase_url, supabase_key, user_id, dry_run)

    # Migrate notes first (to get IDs for relations)
    migrator.migrate_notes(notes, stats)

    # Then migrate relations
    migrator.migrate_relations(all_relations, stats)

    # Finally migrate sessions
    if sessions:
        migrator.migrate_sessions(sessions, stats)

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Obsidian vault and SQLite data to Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run to preview migration
    python migrate_to_supabase.py --vault-path ~/brain --dry-run

    # Full migration
    python migrate_to_supabase.py --vault-path ~/brain

    # Include SQLite sessions
    python migrate_to_supabase.py --vault-path ~/brain --sqlite-db ~/sessions.db

Environment Variables:
    SUPABASE_URL        - Supabase project URL (required)
    SUPABASE_KEY        - Supabase service role key (required)
    MIGRATION_USER_ID   - UUID of user to assign notes to (required)
        """,
    )

    parser.add_argument(
        "--vault-path",
        type=Path,
        required=True,
        help="Path to the Obsidian vault directory",
    )
    parser.add_argument(
        "--sqlite-db",
        type=Path,
        help="Path to SQLite database with sessions data",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without inserting data",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=["node_modules", ".git", ".obsidian", ".trash", "__pycache__", ".venv", "venv"],
        help="Patterns to exclude from migration",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load environment variables
    if args.env_file.exists():
        load_dotenv(args.env_file)
        logger.info(f"Loaded environment from {args.env_file}")

    # Get required environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    user_id = os.getenv("MIGRATION_USER_ID")

    # Validate environment
    missing = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not supabase_key:
        missing.append("SUPABASE_KEY")
    if not user_id:
        missing.append("MIGRATION_USER_ID")

    if missing and not args.dry_run:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Set these in your environment or in a .env file")
        sys.exit(1)

    # For dry run, use placeholders if not set
    if args.dry_run:
        supabase_url = supabase_url or "https://example.supabase.co"
        supabase_key = supabase_key or "example-key"
        user_id = user_id or str(uuid.uuid4())

    # Validate vault path
    if not args.vault_path.exists():
        logger.error(f"Vault path does not exist: {args.vault_path}")
        sys.exit(1)

    if not args.vault_path.is_dir():
        logger.error(f"Vault path is not a directory: {args.vault_path}")
        sys.exit(1)

    # Run migration
    logger.info("=" * 60)
    logger.info("Obsidian-Memory Migration to Supabase")
    logger.info("=" * 60)
    logger.info(f"Vault path: {args.vault_path}")
    logger.info(f"SQLite DB: {args.sqlite_db or 'None'}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Exclude patterns: {args.exclude}")
    logger.info("=" * 60)

    try:
        stats = run_migration(
            vault_path=args.vault_path,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            user_id=user_id,
            sqlite_db=args.sqlite_db,
            dry_run=args.dry_run,
            exclude_patterns=args.exclude,
        )

        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        logger.info(f"Total files found: {stats.total_files}")
        logger.info(f"Files processed: {stats.processed_files}")
        logger.info(f"Notes migrated: {stats.successful_notes}/{stats.processed_files}")
        logger.info(f"Notes failed: {stats.failed_notes}")
        logger.info(f"Relations migrated: {stats.successful_relations}/{stats.total_relations}")
        logger.info(f"Relations failed: {stats.failed_relations}")
        logger.info(f"Sessions migrated: {stats.successful_sessions}/{stats.total_sessions}")
        logger.info(f"Sessions failed: {stats.failed_sessions}")

        if stats.errors:
            logger.warning("")
            logger.warning(f"Errors encountered ({len(stats.errors)}):")
            for error in stats.errors[:10]:  # Show first 10 errors
                logger.warning(f"  - {error}")
            if len(stats.errors) > 10:
                logger.warning(f"  ... and {len(stats.errors) - 10} more errors")

        # Exit with error code if there were failures
        if stats.failed_notes > 0 or stats.failed_relations > 0 or stats.failed_sessions > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
