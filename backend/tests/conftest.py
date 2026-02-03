"""Pytest fixtures for Obsidian-Memory backend tests."""

from __future__ import annotations

import os

# Disable rate limiting in tests so API tests do not get 429 (all requests from 127.0.0.1)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

if TYPE_CHECKING:
    from app.services.search_index import SearchIndex


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_vault(temp_dir: Path) -> Path:
    """Create a sample vault structure for testing."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    # Create memory folder structure
    mem_folder = vault_path / "_claude-mem"
    (mem_folder / "projects" / "test-project" / "decisions").mkdir(parents=True)
    (mem_folder / "projects" / "test-project" / "errors").mkdir(parents=True)
    (mem_folder / "projects" / "test-project" / "knowledge").mkdir(parents=True)
    (mem_folder / "global" / "patterns").mkdir(parents=True)

    # Create sample notes
    sample_note = vault_path / "sample-note.md"
    sample_note.write_text(
        """---
title: Sample Note
type: note
project: test-project
tags:
  - test
  - sample
---

# Sample Note

This is a sample note for testing.

## Observations

- [fact] This is a test fact #testing
- [tip] Always write tests #best-practice (important)

## Relations

- related_to [[Other Note]]
- depends_on [[Dependency]]
"""
    )

    return vault_path


@pytest.fixture
def sample_markdown() -> str:
    """Sample markdown content for parser tests."""
    return """---
title: Test Note
type: decision
project: api-service
permalink: test-note
tags:
  - test
  - parser
---

# Test Note

## Context

- [decision] Chose option A over option B #architecture
- [reason] Better performance characteristics #performance (benchmarked)

## Relations

- depends_on [[Prerequisite]]
- enables [[Downstream Feature]]

## Content

Some regular content with a [[wikilink]] and [[Another Link|display text]].
"""


@pytest.fixture
def sample_frontmatter() -> dict:
    """Sample frontmatter data."""
    return {
        "title": "Test Note",
        "type": "decision",
        "project": "api-service",
        "permalink": "test-note",
        "tags": ["test", "parser"],
    }


@pytest_asyncio.fixture
async def db_path(temp_dir: Path) -> AsyncGenerator[Path, None]:
    """Create a temporary database path."""
    db_file = temp_dir / "test_index.db"
    yield db_file
    # Cleanup handled by temp_dir fixture


async def index_vault_from_path(
    search_index: SearchIndex,
    vault_path: Path,
    vault_name: str,
) -> None:
    """Index all .md files in a vault path into the search index (for graph/backlinks tests)."""
    from app.models.search import IndexedNote
    from app.services.markdown_parser import MarkdownParser
    from app.services.search_index import compute_file_hash

    parser = MarkdownParser()
    notes: list[IndexedNote] = []
    for f in sorted(vault_path.rglob("*.md")):
        content = f.read_text()
        parsed = parser.parse(content)
        rel_path = str(f.relative_to(vault_path))
        notes.append(
            IndexedNote(
                vault_name=vault_name,
                relative_path=rel_path,
                permalink=parsed.frontmatter.permalink,
                title=parsed.frontmatter.title,
                note_type=parsed.frontmatter.type.value,
                project=parsed.frontmatter.project,
                content=content,
                tags=parsed.frontmatter.tags,
                observations=parsed.observations,
                relations=parsed.relations,
                wikilinks=parsed.wikilinks,
                file_hash=compute_file_hash(content),
            )
        )
    if notes:
        await search_index.index_vault(vault_name, notes)
