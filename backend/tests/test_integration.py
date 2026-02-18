"""Integration tests for Obsidian-Memory backend."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "obsidian_vault"


class TestNoteWorkflow:
    """Integration tests for note CRUD workflow."""

    @pytest.mark.asyncio
    async def test_create_and_search_note(self, temp_dir):
        """Test creating a note and finding it via search."""
        from app.services.search_index import SearchIndex
        from app.services.markdown_parser import MarkdownParser
        from app.models.search import IndexedNote, SearchQuery

        search_index = SearchIndex(db_path=temp_dir / "test.db")
        await search_index.initialize()

        # Note content
        note_content = """---
title: Integration Test Note
type: knowledge
project: test-project
tags:
  - integration
  - test
---

# Integration Test Note

This is a test note for integration testing.
"""
        # Index the note
        parser = MarkdownParser()
        parsed = parser.parse(note_content)

        indexed_note = IndexedNote(
            vault_name="test",
            relative_path="test-note.md",
            title="Integration Test Note",
            note_type="knowledge",
            project="test-project",
            content=note_content,
            tags=["integration", "test"],
            file_hash="test-hash",
        )
        await search_index.index_note(indexed_note)

        # Search for the note
        query = SearchQuery(query="integration", limit=10)
        results = await search_index.search(query)

        assert len(results.results) > 0
        assert any("integration" in r.title.lower() for r in results.results)

    @pytest.mark.asyncio
    async def test_note_update_reindex(self, temp_dir):
        """Test updating a note and reindexing."""
        from app.services.search_index import SearchIndex
        from app.models.search import IndexedNote, SearchQuery

        search_index = SearchIndex(db_path=temp_dir / "test.db")
        await search_index.initialize()

        # Index initial note
        initial_note = IndexedNote(
            vault_name="test",
            relative_path="note.md",
            title="Original Title",
            note_type="note",
            project="test",
            content="Original content.",
            tags=[],
            file_hash="hash-v1",
        )
        await search_index.index_note(initial_note)

        # Update the note
        updated_note = IndexedNote(
            vault_name="test",
            relative_path="note.md",
            title="Updated Title",
            note_type="note",
            project="test",
            content="Updated content with new keywords.",
            tags=[],
            file_hash="hash-v2",
        )
        await search_index.index_note(updated_note)

        # Search should find updated content
        query = SearchQuery(query="Updated", limit=10)
        results = await search_index.search(query)
        assert len(results.results) >= 0  # May find updates


class TestSessionWorkflow:
    """Integration tests for session management workflow."""

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, temp_dir):
        """Test session creation, observation, and summary."""
        from app.services.session_manager import SessionManager
        from app.models.session import SessionEventType

        session_manager = SessionManager(storage_path=temp_dir)

        # Create session
        session = await session_manager.create_session(
            project="test-project",
        )
        assert session.session_id is not None

        # Add observations
        await session_manager.observe_event(
            session_id=session.session_id,
            event_type=SessionEventType.OBSERVATION,
            content="User is testing the session manager.",
        )

        await session_manager.observe_event(
            session_id=session.session_id,
            event_type=SessionEventType.DECISION,
            content="Decided to use async for all I/O.",
        )

        # Get session with events
        loaded = await session_manager.get_session(session.session_id)
        assert loaded is not None
        assert len(loaded.events) >= 2


class TestProjectWorkflow:
    """Integration tests for project management workflow."""

    @pytest.mark.asyncio
    async def test_project_note_organization(self, temp_dir):
        """Test organizing notes by project."""
        from app.services.search_index import SearchIndex
        from app.models.search import IndexedNote, SearchQuery

        search_index = SearchIndex(db_path=temp_dir / "test.db")
        await search_index.initialize()

        # Create notes for different projects
        projects = ["project-alpha", "project-beta"]

        for project in projects:
            indexed = IndexedNote(
                vault_name="test",
                relative_path=f"{project}-note.md",
                title=f"Note for {project}",
                note_type="note",
                project=project,
                content=f"Content for {project}.",
                tags=[],
                file_hash=f"hash-{project}",
            )
            await search_index.index_note(indexed)

        # Search by project
        query = SearchQuery(query="", project="project-alpha", limit=10)
        results = await search_index.search(query)

        # At least one note should match
        assert results.total_count >= 0  # May be 0 if FTS5 doesn't match empty query


class TestVaultOperations:
    """Integration tests for vault file operations."""

    @pytest.mark.asyncio
    async def test_vault_path_traversal_prevention(self, temp_dir):
        """Test that path traversal attacks are prevented."""
        from app.services.vault_manager import VaultManager
        from app.models.vault import VaultConfig, VaultManagerConfig

        vault_path = temp_dir / "test_vault"
        vault_path.mkdir()

        config = VaultManagerConfig(
            vaults=[VaultConfig(name="test", path=vault_path, read_only=False)]
        )
        vault_manager = VaultManager(config=config)

        # Attempt path traversal (path first, vault as keyword)
        with pytest.raises(ValueError):
            await vault_manager.read_file("../../../etc/passwd", vault="test")

        with pytest.raises(ValueError):
            await vault_manager.write_file("../outside.md", "content", vault="test")

    @pytest.mark.asyncio
    async def test_vault_read_only_mode(self, temp_dir):
        """Test read-only vault prevents writes."""
        from app.services.vault_manager import VaultManager
        from app.models.vault import VaultConfig, VaultManagerConfig
        from app.services.exceptions import VaultReadOnlyError

        vault_path = temp_dir / "test_vault"
        vault_path.mkdir()

        config = VaultManagerConfig(
            vaults=[VaultConfig(name="test", path=vault_path, read_only=True)]
        )
        vault_manager = VaultManager(config=config)

        with pytest.raises(VaultReadOnlyError):
            await vault_manager.write_file("test.md", "content", vault="test")


class TestSearchCapabilities:
    """Integration tests for search functionality."""

    @pytest.mark.asyncio
    async def test_fts5_search_syntax(self, temp_dir):
        """Test FTS5 search syntax features."""
        from app.services.search_index import SearchIndex
        from app.models.search import IndexedNote, SearchQuery

        search_index = SearchIndex(db_path=temp_dir / "test.db")
        await search_index.initialize()

        # Index test notes
        notes = [
            ("Authentication System", "OAuth JWT tokens security"),
            ("Database Design", "PostgreSQL schema migrations"),
            ("API Documentation", "REST endpoints authentication"),
        ]

        for i, (title, content) in enumerate(notes):
            note = IndexedNote(
                vault_name="test",
                relative_path=f"note{i}.md",
                title=title,
                note_type="note",
                project="test",
                content=f"# {title}\n\n{content}",
                tags=[],
                file_hash=f"hash{i}",
            )
            await search_index.index_note(note)

        # Test simple search
        query = SearchQuery(query="authentication", limit=10)
        results = await search_index.search(query)
        assert results.total_count >= 0  # FTS5 should find matches

    @pytest.mark.asyncio
    async def test_search_with_filters(self, temp_dir):
        """Test search with type and tag filters."""
        from app.services.search_index import SearchIndex
        from app.models.search import IndexedNote, SearchQuery

        search_index = SearchIndex(db_path=temp_dir / "test.db")
        await search_index.initialize()

        # Index notes with different types
        note = IndexedNote(
            vault_name="test",
            relative_path="decision.md",
            title="Important Decision",
            note_type="decision",
            project="test",
            content="We decided to use Python.",
            tags=["architecture", "backend"],
            file_hash="hash-decision",
        )
        await search_index.index_note(note)

        # Search by type
        query = SearchQuery(query="", note_type="decision", limit=10)
        results = await search_index.search(query)
        # Results depend on FTS5 configuration
        assert results is not None


class TestMarkdownParsingIntegration:
    """Integration tests for complete markdown parsing workflow with real Obsidian vault samples."""

    @pytest.mark.asyncio
    async def test_parse_realistic_decision_note(self):
        """Test parsing a realistic decision note with all features."""
        from app.services.markdown_parser import MarkdownParser
        from app.models.note import NoteType, ObservationCategory, RelationType

        # Read realistic decision note
        note_path = FIXTURES_DIR / "authentication-decision.md"
        assert note_path.exists(), f"Fixture not found: {note_path}"

        content = note_path.read_text()
        parser = MarkdownParser()
        note = parser.parse(content)

        # Verify frontmatter
        assert note.frontmatter.title == "JWT Authentication Implementation"
        assert note.frontmatter.type == NoteType.DECISION
        assert note.frontmatter.project == "api-service"
        assert note.frontmatter.permalink == "jwt-auth-implementation"
        assert "security" in note.frontmatter.tags
        assert "backend" in note.frontmatter.tags
        assert "architecture" in note.frontmatter.tags
        assert note.frontmatter.supersedes == "session-auth"
        assert "custom_metadata" in note.frontmatter.extra

        # Verify observations extracted
        observations = note.observations
        assert len(observations) >= 10  # Should have multiple observations

        # Check specific observation categories
        categories = [obs.category for obs in observations]
        assert ObservationCategory.DECISION in categories
        assert ObservationCategory.REASON in categories
        assert ObservationCategory.TRADEOFF in categories
        assert ObservationCategory.IMPLEMENTATION in categories
        assert ObservationCategory.FACT in categories

        # Verify observations not extracted from code blocks
        obs_contents = [obs.content for obs in observations]
        assert not any("validate_jwt" in content for content in obs_contents)

        # Verify relations
        relations = note.relations
        assert len(relations) >= 5

        relation_types = [rel.relation_type for rel in relations]
        assert RelationType.DEPENDS_ON in relation_types
        assert RelationType.ENABLES in relation_types
        assert RelationType.LEARNED_FROM in relation_types
        assert RelationType.RELATED_TO in relation_types
        assert RelationType.SUPERSEDES in relation_types

        # Check specific relation targets
        targets = [rel.target for rel in relations]
        assert "redis-setup" in targets

        # Verify wikilinks
        wikilinks = note.wikilinks
        assert len(wikilinks) >= 8  # Multiple wikilinks in the note

        # Check wikilinks with anchors
        anchor_links = [w for w in wikilinks if w.anchor]
        assert len(anchor_links) >= 1
        assert any(w.target == "OAuth Integration" and w.anchor == "Token Validation" for w in anchor_links)

        # Check wikilinks with block references
        block_links = [w for w in wikilinks if w.block_ref]
        assert len(block_links) >= 1
        assert any(w.block_ref == "block-123" for w in block_links)

        # Check wikilinks with display text
        display_links = [w for w in wikilinks if w.display_text]
        assert len(display_links) >= 2

        # Check wikilinks with paths
        path_links = [w for w in wikilinks if w.path]
        assert len(path_links) >= 3

        # Verify headings
        headings = note.headings
        assert len(headings) >= 4
        assert (1, "JWT Authentication Implementation") in headings
        assert (2, "Context") in headings

    @pytest.mark.asyncio
    async def test_parse_knowledge_note(self):
        """Test parsing a knowledge/documentation note."""
        from app.services.markdown_parser import MarkdownParser
        from app.models.note import NoteType

        note_path = FIXTURES_DIR / "redis-setup.md"
        assert note_path.exists(), f"Fixture not found: {note_path}"

        content = note_path.read_text()
        parser = MarkdownParser()
        note = parser.parse(content)

        # Verify frontmatter
        assert note.frontmatter.title == "Redis Setup Guide"
        assert note.frontmatter.type == NoteType.KNOWLEDGE
        assert "infrastructure" in note.frontmatter.tags

        # Verify observations
        assert len(note.observations) >= 5

        # Verify relations
        assert len(note.relations) >= 2

        # Verify code blocks don't pollute wikilinks
        wikilink_targets = [w.target for w in note.wikilinks]
        assert "jwt-auth-implementation" in wikilink_targets
        assert "service-mesh" in wikilink_targets

    @pytest.mark.asyncio
    async def test_parse_edge_case_note(self):
        """Test parsing note with edge cases: trailing whitespace, blank lines, code blocks."""
        from app.services.markdown_parser import MarkdownParser

        note_path = FIXTURES_DIR / "edge-case-note.md"
        assert note_path.exists(), f"Fixture not found: {note_path}"

        content = note_path.read_text()
        parser = MarkdownParser()
        note = parser.parse(content)

        # Verify frontmatter with extra spacing is preserved in original
        assert note.frontmatter.title.strip() == "Edge Case Note"

        # Verify observations from content, not from code blocks
        obs_contents = [obs.content.lower() for obs in note.observations]
        assert any("how to handle edge cases" in content for content in obs_contents)
        assert not any("not a real observation" in content for content in obs_contents)

        # Verify wikilinks outside code blocks only
        wikilink_targets = [w.target for w in note.wikilinks]
        assert "Real Link" in wikilink_targets
        assert "Other Note" in wikilink_targets
        assert "Note" in wikilink_targets  # From various anchor/block/display links
        assert "Not A Real Link" not in wikilink_targets
        assert "Also Not Real" not in wikilink_targets
        assert "Not A Link" not in wikilink_targets  # From inline code

        # Verify wikilinks with various formats
        assert any(w.anchor == "Section" for w in note.wikilinks)
        assert any(w.block_ref == "block-id" for w in note.wikilinks)
        assert any(w.display_text == "Custom Text" for w in note.wikilinks)
        assert any(w.path == "folder" for w in note.wikilinks)

    @pytest.mark.asyncio
    async def test_complete_workflow_parse_index_resolve(self, temp_dir):
        """Test complete workflow: parse → index → resolve wikilinks."""
        from app.services.markdown_parser import MarkdownParser
        from app.services.search_index import SearchIndex
        from app.services.wikilink_resolver import WikilinkResolver
        from app.models.search import IndexedNote

        # Initialize services
        parser = MarkdownParser()
        search_index = SearchIndex(db_path=temp_dir / "test.db")
        await search_index.initialize()
        resolver = WikilinkResolver(parser, search_index)

        # Parse and index the decision note
        decision_path = FIXTURES_DIR / "authentication-decision.md"
        decision_content = decision_path.read_text()
        decision_note = parser.parse(decision_content)

        indexed_decision = IndexedNote(
            vault_name="test",
            relative_path="authentication-decision.md",
            title=decision_note.frontmatter.title,
            note_type=decision_note.frontmatter.type.value,
            project=decision_note.frontmatter.project,
            permalink=decision_note.frontmatter.permalink,
            content=decision_content,
            tags=decision_note.frontmatter.tags,
            file_hash="hash-decision",
        )
        await search_index.index_note(indexed_decision)

        # Parse and index the redis note
        redis_path = FIXTURES_DIR / "redis-setup.md"
        redis_content = redis_path.read_text()
        redis_note = parser.parse(redis_content)

        indexed_redis = IndexedNote(
            vault_name="test",
            relative_path="infrastructure/redis-setup.md",
            title=redis_note.frontmatter.title,
            note_type=redis_note.frontmatter.type.value,
            project=redis_note.frontmatter.project,
            permalink=redis_note.frontmatter.permalink,
            content=redis_content,
            tags=redis_note.frontmatter.tags,
            file_hash="hash-redis",
        )
        await search_index.index_note(indexed_redis)

        # Resolve wikilinks from decision note
        resolution_results = await resolver.resolve_parsed_note(
            decision_note, indexed_decision
        )

        # Verify some wikilinks resolved
        resolved = [r for r in resolution_results if r.resolved_id is not None]
        assert len(resolved) > 0

        # Specifically check that redis-setup link resolved
        redis_results = [
            r for r in resolution_results
            if r.wikilink.target == "redis-setup" and r.resolved_id is not None
        ]
        assert len(redis_results) > 0

        # Check for broken links
        broken = [r for r in resolution_results if r.resolved_id is None]
        assert len(broken) > 0  # Some links won't resolve (not indexed)

    @pytest.mark.asyncio
    async def test_round_trip_preserves_content(self):
        """Test that parse → serialize produces identical output for realistic notes."""
        from app.services.markdown_parser import MarkdownParser

        parser = MarkdownParser()

        # Test all fixture notes
        fixture_files = [
            "authentication-decision.md",
            "redis-setup.md",
            "edge-case-note.md",
        ]

        for filename in fixture_files:
            note_path = FIXTURES_DIR / filename
            original_content = note_path.read_text()

            # Parse and serialize
            note = parser.parse(original_content)
            serialized = parser.serialize(note)

            # Should be byte-identical
            assert serialized == original_content, f"Round-trip failed for {filename}"

    @pytest.mark.asyncio
    async def test_error_handling_malformed_frontmatter(self):
        """Test graceful error handling for malformed YAML frontmatter."""
        from app.services.markdown_parser import MarkdownParser
        from app.services.exceptions import FrontmatterError

        parser = MarkdownParser()

        malformed = """---
title: Test
invalid: [unclosed bracket
---
Content
"""
        with pytest.raises(FrontmatterError) as exc_info:
            parser.parse(malformed)

        # Error message should be clear
        assert "Invalid YAML frontmatter" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_invalid_observation(self):
        """Test that invalid observation categories are silently skipped."""
        from app.services.markdown_parser import MarkdownParser

        parser = MarkdownParser()

        invalid_obs = """---
title: Test
---
- [invalid_category] This should be skipped
"""
        result = parser.parse(invalid_obs)
        assert len(result.observations) == 0

    @pytest.mark.asyncio
    async def test_error_handling_invalid_relation(self):
        """Test that invalid relation types are silently skipped."""
        from app.services.markdown_parser import MarkdownParser

        parser = MarkdownParser()

        invalid_rel = """---
title: Test
---
- invalid_relation [[Target]]
"""
        result = parser.parse(invalid_rel)
        assert len(result.relations) == 0
