"""Pytest fixtures for Obsidian-Memory backend tests."""

import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio


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
