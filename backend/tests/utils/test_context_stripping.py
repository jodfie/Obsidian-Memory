"""Tests for context stripping utility."""

import re

import pytest

from app.utils.context_stripping import (
    CONTEXT_BLOCK_END,
    CONTEXT_BLOCK_PATTERN,
    CONTEXT_BLOCK_START,
    MIN_CONTENT_LENGTH,
    has_meaningful_content,
    strip_injected_context,
)


class TestConstants:
    """Verify markers and pattern are defined correctly."""

    def test_markers_are_html_comments(self):
        assert CONTEXT_BLOCK_START.startswith("<!--")
        assert CONTEXT_BLOCK_START.endswith("-->")
        assert CONTEXT_BLOCK_END.startswith("<!--")
        assert CONTEXT_BLOCK_END.endswith("-->")

    def test_pattern_is_compiled(self):
        assert isinstance(CONTEXT_BLOCK_PATTERN, re.Pattern)

    def test_min_content_length_is_positive(self):
        assert MIN_CONTENT_LENGTH > 0


class TestStripInjectedContext:
    """Tests for strip_injected_context function."""

    def test_single_block_removal(self):
        content = f"Before {CONTEXT_BLOCK_START}injected{CONTEXT_BLOCK_END} after"
        result = strip_injected_context(content)
        assert "injected" not in result
        assert "Before" in result
        assert "after" in result

    def test_multiple_blocks_removal(self):
        content = (
            f"Text1 {CONTEXT_BLOCK_START}ctx1{CONTEXT_BLOCK_END} "
            f"Text2 {CONTEXT_BLOCK_START}ctx2{CONTEXT_BLOCK_END} Text3"
        )
        result = strip_injected_context(content)
        assert "ctx1" not in result
        assert "ctx2" not in result
        assert "Text1" in result
        assert "Text2" in result
        assert "Text3" in result

    def test_nested_blocks(self):
        """Non-greedy regex stops at first end marker, handling nesting."""
        content = (
            f"{CONTEXT_BLOCK_START}outer "
            f"{CONTEXT_BLOCK_START}inner{CONTEXT_BLOCK_END}"
            f" still outer{CONTEXT_BLOCK_END}"
        )
        result = strip_injected_context(content)
        # First match: start -> first end (removes "outer ...inner")
        # "still outer" + trailing end marker may remain
        assert "inner" not in result

    def test_malformed_missing_end_tag(self):
        """Unclosed blocks are left as-is (no crash)."""
        content = f"Text {CONTEXT_BLOCK_START}unclosed block remains"
        result = strip_injected_context(content)
        assert "Text" in result
        assert "unclosed" in result

    def test_no_blocks_passthrough(self):
        content = "Normal content with no context blocks."
        assert strip_injected_context(content) == content

    def test_special_regex_chars_inside_block(self):
        content = f"Text {CONTEXT_BLOCK_START}$100 *.txt foo+bar (parens){CONTEXT_BLOCK_END} after"
        result = strip_injected_context(content)
        assert "$100" not in result
        assert "*.txt" not in result
        assert "foo+bar" not in result
        assert "after" in result

    def test_empty_string(self):
        assert strip_injected_context("") == ""

    def test_none_returns_empty(self):
        assert strip_injected_context(None) == ""

    def test_whitespace_normalization(self):
        content = "Line1\n\n\n\n\nLine2"
        result = strip_injected_context(content)
        assert result == "Line1\n\nLine2"

    def test_multiline_block(self):
        content = (
            f"Before\n{CONTEXT_BLOCK_START}\n"
            f"Line 1 of context\nLine 2 of context\n"
            f"{CONTEXT_BLOCK_END}\nAfter"
        )
        result = strip_injected_context(content)
        assert "Line 1 of context" not in result
        assert "Line 2 of context" not in result
        assert "Before" in result
        assert "After" in result

    def test_only_context_block_returns_empty(self):
        content = f"{CONTEXT_BLOCK_START}only context{CONTEXT_BLOCK_END}"
        assert strip_injected_context(content) == ""

    def test_block_at_start(self):
        content = f"{CONTEXT_BLOCK_START}ctx{CONTEXT_BLOCK_END} trailing text"
        result = strip_injected_context(content)
        assert result == "trailing text"

    def test_block_at_end(self):
        content = f"leading text {CONTEXT_BLOCK_START}ctx{CONTEXT_BLOCK_END}"
        result = strip_injected_context(content)
        assert result == "leading text"


class TestHasMeaningfulContent:
    """Tests for has_meaningful_content function."""

    def test_enough_content(self):
        assert has_meaningful_content("This is meaningful content.") is True

    def test_too_short_after_strip(self):
        content = f"{CONTEXT_BLOCK_START}big block{CONTEXT_BLOCK_END} hi"
        assert has_meaningful_content(content) is False  # "hi" = 2 chars

    def test_exactly_at_threshold(self):
        filler = "a" * MIN_CONTENT_LENGTH
        content = f"{CONTEXT_BLOCK_START}ctx{CONTEXT_BLOCK_END}{filler}"
        assert has_meaningful_content(content) is True

    def test_one_below_threshold(self):
        filler = "a" * (MIN_CONTENT_LENGTH - 1)
        content = f"{CONTEXT_BLOCK_START}ctx{CONTEXT_BLOCK_END}{filler}"
        assert has_meaningful_content(content) is False

    def test_no_blocks_long_content(self):
        assert has_meaningful_content("This has no blocks at all.") is True

    def test_empty_string(self):
        assert has_meaningful_content("") is False

    def test_only_block(self):
        content = f"{CONTEXT_BLOCK_START}nothing real{CONTEXT_BLOCK_END}"
        assert has_meaningful_content(content) is False


class TestSessionManagerIntegration:
    """Integration tests for stripping in session_manager.observe_event."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        from app.services.session_manager import SessionManager
        return SessionManager(storage_path=tmp_path / "sessions")

    @pytest.mark.asyncio
    async def test_observe_strips_context_blocks(self, session_manager):
        session = await session_manager.create_session(project="test")
        sid = session.session_id

        content = f"User decided to use JWT. {CONTEXT_BLOCK_START}injected memory{CONTEXT_BLOCK_END}"
        await session_manager.observe_event(sid, "observation", content)

        session = await session_manager.get_session(sid)
        assert len(session.events) == 1
        assert "injected memory" not in session.events[0].content
        assert "User decided to use JWT." in session.events[0].content

    @pytest.mark.asyncio
    async def test_observe_skips_short_content_after_strip(self, session_manager):
        session = await session_manager.create_session(project="test")
        sid = session.session_id

        # Content is ONLY a context block -> empty after strip
        content = f"{CONTEXT_BLOCK_START}all injected{CONTEXT_BLOCK_END}"
        result = await session_manager.observe_event(sid, "observation", content)

        assert len(result.events) == 0

    @pytest.mark.asyncio
    async def test_observe_passes_through_normal_content(self, session_manager):
        session = await session_manager.create_session(project="test")
        sid = session.session_id

        content = "Normal observation without any context blocks."
        await session_manager.observe_event(sid, "observation", content)

        session = await session_manager.get_session(sid)
        assert len(session.events) == 1
        assert session.events[0].content == content

    @pytest.mark.asyncio
    async def test_observe_mixed_events(self, session_manager):
        """Mix of events with/without context blocks."""
        session = await session_manager.create_session(project="test")
        sid = session.session_id

        # Event 1: normal
        await session_manager.observe_event(sid, "observation", "First real event here.")
        # Event 2: only context block (should be skipped)
        await session_manager.observe_event(
            sid, "observation",
            f"{CONTEXT_BLOCK_START}only injected{CONTEXT_BLOCK_END}",
        )
        # Event 3: mixed (should store stripped version)
        await session_manager.observe_event(
            sid, "decision",
            f"Chose PostgreSQL. {CONTEXT_BLOCK_START}memory{CONTEXT_BLOCK_END}",
        )

        session = await session_manager.get_session(sid)
        assert len(session.events) == 2  # Event 2 was skipped
        assert session.events[0].content == "First real event here."
        assert session.events[1].content == "Chose PostgreSQL."
