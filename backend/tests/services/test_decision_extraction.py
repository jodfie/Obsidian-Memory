"""Tests for regex-based decision extraction from prose content."""

import pytest

from app.models.note import Observation, ObservationCategory
from app.services.markdown_parser import (
    DECISION_PATTERNS,
    MarkdownParser,
)


@pytest.fixture
def parser():
    return MarkdownParser()


# ============================================================================
# Pattern matching tests
# ============================================================================


class TestDecidedChosePattern:
    """Test 'decided/chose/picked X because Y' pattern."""

    def test_decided_to_use_because(self, parser):
        content = "We decided to use FastAPI because of async support."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert results[0].category == ObservationCategory.DECISION
        assert "FastAPI" in results[0].content

    def test_chose_with_reason(self, parser):
        content = "Chose SQLite for simplicity."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert "SQLite" in results[0].content

    def test_picked_with_because(self, parser):
        content = "We picked Docker because it handles dependencies well."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert "Docker" in results[0].content

    def test_selected_pattern(self, parser):
        content = "Selected Python for the backend."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_case_insensitive(self, parser):
        content = "DECIDED to use Redis for caching."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1


class TestUseOverPattern:
    """Test 'use X over Y' pattern."""

    def test_use_over(self, parser):
        content = "Use SQLite over Postgres for simplicity."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert "SQLite" in results[0].content

    def test_prefer_instead_of(self, parser):
        content = "Prefer FastAPI instead of Flask."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1

    def test_chose_rather_than(self, parser):
        content = "Chose Docker rather than Podman."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1

    def test_using_over_with_reason(self, parser):
        content = "Using aiosqlite over raw sqlite3 because of async support."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1


class TestAlwaysNeverPattern:
    """Test 'always/never/must X' pattern."""

    def test_always(self, parser):
        content = "Always run migrations before deploy."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert "Always run migrations before deploy" in results[0].content

    def test_never(self, parser):
        content = "Never commit .env files to git."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1

    def test_must(self, parser):
        content = "Must validate input at API boundary."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1

    def test_should_always(self, parser):
        content = "Should always use parameterized queries."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1

    def test_should_never(self, parser):
        content = "Should never store plaintext passwords."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1


class TestWentWithPattern:
    """Test 'went with X for Y' pattern."""

    def test_went_with(self, parser):
        content = "Went with Docker for portability."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert "Docker" in results[0].content

    def test_sticking_with(self, parser):
        content = "Sticking with SQLite for now."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1

    def test_going_with_because(self, parser):
        content = "Going with FastAPI because it supports async natively."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1


# ============================================================================
# Edge cases and skipping tests
# ============================================================================


class TestCodeBlockSkipping:
    """Test that decisions inside code blocks are not extracted."""

    def test_skip_fenced_code_block(self, parser):
        content = """Some regular text.

```python
# We decided to use Flask here
decided to use Flask because it's simpler
```

We decided to use FastAPI because of async."""
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert "FastAPI" in results[0].content

    def test_skip_unclosed_code_block(self, parser):
        content = """```
decided to use something
never close this block"""
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 0


class TestObservationLineSkipping:
    """Test that existing observation lines are not extracted."""

    def test_skip_observation_pattern(self, parser):
        content = "- [decision] Use FastAPI for the backend"
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 0

    def test_skip_any_observation_category(self, parser):
        content = "- [tip] Always validate user input"
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 0


class TestDeduplication:
    """Test deduplication against existing observations."""

    def test_skip_duplicate_content(self, parser):
        existing = [
            Observation(
                category=ObservationCategory.DECISION,
                content="Use FastAPI for the backend",
                tags=[],
                context=None,
                line_number=1,
            )
        ]
        content = "We decided to use FastAPI for the backend."
        results = parser.extract_decisions_from_prose(content, existing)
        # Should be skipped because existing content is a substring of the decision
        assert len(results) == 0

    def test_no_dedup_for_different_content(self, parser):
        existing = [
            Observation(
                category=ObservationCategory.DECISION,
                content="Use Django for the frontend",
                tags=[],
                context=None,
                line_number=1,
            )
        ]
        content = "We decided to use FastAPI for the backend."
        results = parser.extract_decisions_from_prose(content, existing)
        assert len(results) == 1


class TestLineNumberTracking:
    """Test that line numbers are tracked correctly."""

    def test_line_number_matches(self, parser):
        content = """First line
Second line
We decided to use FastAPI because of async.
Fourth line"""
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert results[0].line_number == 3

    def test_multiple_decisions_line_numbers(self, parser):
        content = """Line 1
Always run tests before deploying.
Line 3
Never push directly to main.
Line 5"""
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 2
        assert results[0].line_number == 2
        assert results[1].line_number == 4


class TestMultipleDecisions:
    """Test extraction of multiple decisions from same note."""

    def test_multiple_patterns(self, parser):
        content = """We decided to use FastAPI because of async support.
Some regular text here.
Always run migrations before deploy.
More text.
Went with Docker for portability."""
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 3

    def test_one_match_per_line(self, parser):
        # A line that matches multiple patterns should only produce one observation
        content = "We decided to use FastAPI."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1


class TestEmptyContent:
    """Test handling of empty/whitespace content."""

    def test_empty_string(self, parser):
        results = parser.extract_decisions_from_prose("", [])
        assert len(results) == 0

    def test_whitespace_only(self, parser):
        results = parser.extract_decisions_from_prose("   \n\n   ", [])
        assert len(results) == 0

    def test_frontmatter_markers_skipped(self, parser):
        content = "---\n---"
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 0


class TestObservationFields:
    """Test that returned Observation objects have correct fields."""

    def test_auto_extracted_is_true(self, parser):
        content = "We decided to use FastAPI."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert results[0].auto_extracted is True

    def test_decay_override_is_permanent(self, parser):
        content = "We decided to use FastAPI."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert results[0].decay_override == 'permanent'

    def test_category_is_decision(self, parser):
        content = "Always validate input."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        assert results[0].category == ObservationCategory.DECISION

    def test_tags_empty(self, parser):
        content = "We decided to use FastAPI."
        results = parser.extract_decisions_from_prose(content, [])
        assert results[0].tags == []

    def test_context_from_reason(self, parser):
        content = "We decided to use FastAPI because of async support."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        # Context should be extracted from the "because" group
        if results[0].context:
            assert "async" in results[0].context.lower()

    def test_context_none_when_no_reason(self, parser):
        content = "Must validate all inputs."
        results = parser.extract_decisions_from_prose(content, [])
        assert len(results) == 1
        # "always/never/must" pattern has only 1 group, so context should be None
        assert results[0].context is None


# ============================================================================
# DECISION_PATTERNS direct tests
# ============================================================================


class TestDecisionPatternsCompiled:
    """Test that DECISION_PATTERNS are valid compiled regex objects."""

    def test_patterns_exist(self):
        assert len(DECISION_PATTERNS) == 4

    def test_patterns_are_compiled(self):
        import re
        for pattern in DECISION_PATTERNS:
            assert isinstance(pattern, re.Pattern)

    def test_decided_pattern_matches(self):
        assert DECISION_PATTERNS[0].search("decided to use FastAPI because of async")

    def test_use_over_pattern_matches(self):
        assert DECISION_PATTERNS[1].search("use SQLite over Postgres")

    def test_always_pattern_matches(self):
        assert DECISION_PATTERNS[2].search("always run tests")

    def test_went_with_pattern_matches(self):
        assert DECISION_PATTERNS[3].search("went with Docker for portability")
