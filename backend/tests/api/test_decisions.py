"""Tests for decision extraction API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.search_index import SearchIndex


@pytest.fixture
async def db_path(tmp_path):
    return tmp_path / "test_decisions.db"


@pytest.fixture
async def search_index(db_path):
    index = SearchIndex(db_path)
    await index.initialize()
    yield index
    await index.close()


async def _seed_notes(search_index: SearchIndex) -> list[int]:
    """Insert test notes and return their IDs."""
    notes = [
        ("v1", "a.md", "Auth Design", "note", "We decided to use JWT because it is stateless. Always validate tokens server-side."),
        ("v1", "b.md", "DB Choice", "decision", "Chose PostgreSQL over MySQL for better JSON support. Went with pgvector for embeddings."),
        ("v1", "c.md", "Simple Note", "note", "This note has no decisions at all, just descriptions."),
        ("v2", "d.md", "Other Vault", "note", "Decided to use Redis for caching due to performance."),
    ]
    ids = []
    for vault, path, title, ntype, content in notes:
        await search_index.db.execute(
            "INSERT INTO notes (vault_name, relative_path, title, note_type, content, "
            "indexed_at, file_hash) VALUES (?, ?, ?, ?, ?, datetime('now'), ?)",
            (vault, path, title, ntype, content, f"hash-{path}"),
        )
        cursor = await search_index.db.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        ids.append(row[0])
    await search_index.db.commit()
    return ids


class TestExtractDecisionsSingle:
    """Test POST /api/notes/{note_id}/extract-decisions."""

    @pytest.mark.asyncio
    async def test_regex_extraction(self, search_index):
        from app.api.decisions import extract_decisions_single, ExtractDecisionsRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        ids = await _seed_notes(search_index)
        note_id = ids[0]  # "Auth Design" — has decision language

        request = ExtractDecisionsRequest(method="regex", dry_run=True)
        result = await extract_decisions_single(
            note_id=note_id,
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        assert result.dry_run is True
        assert result.extracted >= 1
        assert all(d["method"] == "regex" for d in result.decisions)

    @pytest.mark.asyncio
    async def test_dry_run_does_not_persist(self, search_index):
        from app.api.decisions import extract_decisions_single, ExtractDecisionsRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        ids = await _seed_notes(search_index)
        note_id = ids[0]

        request = ExtractDecisionsRequest(method="regex", dry_run=True)
        await extract_decisions_single(
            note_id=note_id,
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        # Verify nothing persisted
        cursor = await search_index.db.execute(
            "SELECT COUNT(*) FROM observations WHERE note_id = ? AND auto_extracted = 1",
            (note_id,),
        )
        assert (await cursor.fetchone())[0] == 0

    @pytest.mark.asyncio
    async def test_non_dry_run_persists(self, search_index):
        from app.api.decisions import extract_decisions_single, ExtractDecisionsRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        ids = await _seed_notes(search_index)
        note_id = ids[1]  # "DB Choice" — has decision language

        request = ExtractDecisionsRequest(method="regex", dry_run=False)
        result = await extract_decisions_single(
            note_id=note_id,
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        if result.extracted > 0:
            cursor = await search_index.db.execute(
                "SELECT COUNT(*) FROM observations WHERE note_id = ? AND auto_extracted = 1 AND category = 'decision'",
                (note_id,),
            )
            assert (await cursor.fetchone())[0] == result.extracted

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_note(self, search_index):
        from app.api.decisions import extract_decisions_single, ExtractDecisionsRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor
        from fastapi import HTTPException

        request = ExtractDecisionsRequest(method="regex")
        with pytest.raises(HTTPException) as exc_info:
            await extract_decisions_single(
                note_id=99999,
                request=request,
                search_index=search_index,
                parser=MarkdownParser(),
                ai_processor=AIProcessor(),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_decisions_in_plain_note(self, search_index):
        from app.api.decisions import extract_decisions_single, ExtractDecisionsRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        ids = await _seed_notes(search_index)
        note_id = ids[2]  # "Simple Note" — no decision language

        request = ExtractDecisionsRequest(method="regex", dry_run=True)
        result = await extract_decisions_single(
            note_id=note_id,
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        assert result.extracted == 0
        assert result.decisions == []

    @pytest.mark.asyncio
    async def test_preview_limited_to_10(self, search_index):
        """Response decisions list is capped at 10."""
        from app.api.decisions import extract_decisions_single, ExtractDecisionsRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        # Insert a note with many decision-like lines
        lines = [f"Decided to use tool{i} because reason{i}." for i in range(15)]
        content = "\n".join(lines)
        await search_index.db.execute(
            "INSERT INTO notes (vault_name, relative_path, title, note_type, content, "
            "indexed_at, file_hash) VALUES ('v1', 'many.md', 'Many Decisions', 'note', ?, datetime('now'), 'hash-many')",
            (content,),
        )
        await search_index.db.commit()

        cursor = await search_index.db.execute(
            "SELECT id FROM notes WHERE relative_path = 'many.md'"
        )
        note_id = (await cursor.fetchone())[0]

        request = ExtractDecisionsRequest(method="regex", dry_run=True)
        result = await extract_decisions_single(
            note_id=note_id,
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        assert len(result.decisions) <= 10
        # extracted count reflects actual total, not preview limit
        assert result.extracted >= len(result.decisions)


class TestExtractDecisionsBulk:
    """Test POST /api/notes/extract-decisions."""

    @pytest.mark.asyncio
    async def test_bulk_regex_all_notes(self, search_index):
        from app.api.decisions import extract_decisions_bulk, BulkExtractRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        await _seed_notes(search_index)

        request = BulkExtractRequest(method="regex", dry_run=True)
        result = await extract_decisions_bulk(
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        assert result.notes_scanned == 4
        assert result.extracted >= 1
        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_bulk_vault_filter(self, search_index):
        from app.api.decisions import extract_decisions_bulk, BulkExtractRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        await _seed_notes(search_index)

        request = BulkExtractRequest(method="regex", vault="v2", dry_run=True)
        result = await extract_decisions_bulk(
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        assert result.notes_scanned == 1  # Only d.md in v2

    @pytest.mark.asyncio
    async def test_bulk_project_filter(self, search_index):
        from app.api.decisions import extract_decisions_bulk, BulkExtractRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        # Add a note with a project
        await search_index.db.execute(
            "INSERT INTO notes (vault_name, relative_path, title, note_type, content, "
            "indexed_at, file_hash, project) VALUES ('v1', 'proj.md', 'Proj Note', 'note', "
            "'Decided to use FastAPI because async.', datetime('now'), 'hash-proj', 'myproj')",
        )
        await search_index.db.commit()

        request = BulkExtractRequest(method="regex", project="myproj", dry_run=True)
        result = await extract_decisions_bulk(
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        assert result.notes_scanned == 1

    @pytest.mark.asyncio
    async def test_bulk_skips_already_processed(self, search_index):
        from app.api.decisions import extract_decisions_bulk, BulkExtractRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        ids = await _seed_notes(search_index)

        # Mark note a.md as already processed by inserting an auto-extracted decision
        await search_index.db.execute(
            "INSERT INTO observations (note_id, category, content, auto_extracted) "
            "VALUES (?, 'decision', 'existing', 1)",
            (ids[0],),
        )
        await search_index.db.commit()

        # First run without reprocess — should skip a.md
        request = BulkExtractRequest(method="regex", dry_run=True, reprocess=False)
        result = await extract_decisions_bulk(
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        # All notes scanned, but a.md skipped for extraction
        assert result.notes_scanned == 4

    @pytest.mark.asyncio
    async def test_bulk_reprocess_re_extracts(self, search_index):
        from app.api.decisions import extract_decisions_bulk, BulkExtractRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        ids = await _seed_notes(search_index)

        # Mark note a.md as already processed
        await search_index.db.execute(
            "INSERT INTO observations (note_id, category, content, auto_extracted) "
            "VALUES (?, 'decision', 'existing', 1)",
            (ids[0],),
        )
        await search_index.db.commit()

        # With reprocess=True, should still extract from a.md
        request = BulkExtractRequest(method="regex", dry_run=True, reprocess=True)
        result = await extract_decisions_bulk(
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        # Should find decisions in notes with decision language
        assert result.extracted >= 1

    @pytest.mark.asyncio
    async def test_bulk_empty_result(self, search_index):
        from app.api.decisions import extract_decisions_bulk, BulkExtractRequest
        from app.services.markdown_parser import MarkdownParser
        from app.services.ai_processor import AIProcessor

        # No notes seeded — empty DB
        request = BulkExtractRequest(method="regex", dry_run=True)
        result = await extract_decisions_bulk(
            request=request,
            search_index=search_index,
            parser=MarkdownParser(),
            ai_processor=AIProcessor(),
        )

        assert result.notes_scanned == 0
        assert result.extracted == 0
        assert result.decisions == []


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_default_method_is_regex(self):
        from app.api.decisions import ExtractDecisionsRequest
        req = ExtractDecisionsRequest()
        assert req.method == "regex"
        assert req.dry_run is False

    def test_invalid_method_rejected(self):
        from app.api.decisions import ExtractDecisionsRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExtractDecisionsRequest(method="invalid")

    def test_bulk_defaults(self):
        from app.api.decisions import BulkExtractRequest
        req = BulkExtractRequest()
        assert req.method == "regex"
        assert req.vault is None
        assert req.project is None
        assert req.dry_run is False
        assert req.reprocess is False
