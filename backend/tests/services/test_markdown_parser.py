"""Tests for MarkdownParser service."""

from datetime import datetime

import pytest

from app.models.note import (
    NoteType,
    ObservationCategory,
    RelationType,
)
from app.services.exceptions import (
    FrontmatterError,
    InvalidObservationError,
    InvalidRelationError,
)
from app.services.markdown_parser import MarkdownParser


@pytest.fixture
def parser() -> MarkdownParser:
    """Create a MarkdownParser instance."""
    return MarkdownParser()


def test_parse_frontmatter_valid(parser: MarkdownParser) -> None:
    """Test parsing valid frontmatter."""
    content = """---
title: Test Note
type: decision
project: test-project
permalink: test-note
created: 2025-01-15T10:30:00Z
updated: 2025-01-16T14:20:00Z
tags:
  - test
  - parser
---
# Test Note

Content here.
"""
    frontmatter, remaining = parser.parse_frontmatter(content)

    assert frontmatter.title == "Test Note"
    assert frontmatter.type == NoteType.DECISION
    assert frontmatter.project == "test-project"
    assert frontmatter.permalink == "test-note"
    assert frontmatter.tags == ["test", "parser"]
    assert "# Test Note" in remaining
    assert "Content here." in remaining


def test_parse_frontmatter_missing_title(parser: MarkdownParser) -> None:
    """Test parsing frontmatter without title."""
    content = """---
type: note
---
# Content
"""
    frontmatter, _ = parser.parse_frontmatter(content)

    assert frontmatter.title == "Untitled"
    assert frontmatter.permalink is not None  # Auto-generated


def test_parse_frontmatter_extra_fields(parser: MarkdownParser) -> None:
    """Test parsing frontmatter with extra fields."""
    content = """---
title: Test
custom_field: custom_value
another_field: 123
---
Content
"""
    frontmatter, _ = parser.parse_frontmatter(content)

    assert frontmatter.title == "Test"
    assert frontmatter.extra["custom_field"] == "custom_value"
    assert frontmatter.extra["another_field"] == 123


def test_parse_frontmatter_invalid_yaml(parser: MarkdownParser) -> None:
    """Test parsing invalid YAML frontmatter."""
    content = """---
title: Test
invalid: [unclosed
---
Content
"""
    with pytest.raises(FrontmatterError):
        parser.parse_frontmatter(content)


def test_extract_observations_all_categories(parser: MarkdownParser) -> None:
    """Test extracting observations with all categories."""
    content = """- [decision] Chose JWT over sessions
- [reason] Stateless API design
- [tradeoff] Can't revoke tokens easily
- [implementation] Using RS256
- [gotcha] Token refresh needs Redis
- [pattern] Middleware validates on every request
- [tip] Set short expiry
- [fact] JWT is industry standard
- [error] Token validation failed
- [solution] Use refresh tokens
- [experiment] Tried session cookies first
- [resource] https://jwt.io
- [question] How to handle revocation?
- [answer] Use blacklist
"""
    observations = parser.extract_observations(content)

    assert len(observations) == 14
    assert observations[0].category == ObservationCategory.DECISION
    assert observations[1].category == ObservationCategory.REASON
    assert observations[2].category == ObservationCategory.TRADEOFF


def test_extract_observations_with_tags(parser: MarkdownParser) -> None:
    """Test extracting observations with inline tags."""
    content = """- [decision] Chose JWT #security #architecture
- [tip] Set short expiry #security #best-practice
"""
    observations = parser.extract_observations(content)

    assert len(observations) == 2
    assert "security" in observations[0].tags
    assert "architecture" in observations[0].tags
    assert "security" in observations[1].tags
    assert "best-practice" in observations[1].tags


def test_extract_observations_with_context(parser: MarkdownParser) -> None:
    """Test extracting observations with context."""
    content = """- [implementation] Using RS256 (weekly rotation)
- [gotcha] Token refresh needs Redis (for blacklist)
"""
    observations = parser.extract_observations(content)

    assert len(observations) == 2
    assert observations[0].context == "weekly rotation"
    assert observations[1].context == "for blacklist"


def test_extract_observations_invalid_category(parser: MarkdownParser) -> None:
    """Test extracting observation with invalid category."""
    content = """- [invalid] This should fail
"""
    with pytest.raises(InvalidObservationError):
        parser.extract_observations(content)


def test_extract_relations_all_types(parser: MarkdownParser) -> None:
    """Test extracting relations with all types."""
    content = """- depends_on [[redis-setup]]
- enables [[api-gateway-auth]]
- related_to [[user-authentication]]
- learned_from [[session-scaling-issues]]
- supersedes [[old-auth]]
- caused_by [[token-leak]]
- solved_by [[refresh-tokens]]
- part_of [[auth-system]]
- implements [[auth-spec]]
- tests [[auth-service]]
- documents [[auth-api]]
"""
    relations = parser.extract_relations(content)

    assert len(relations) == 11
    assert relations[0].relation_type == RelationType.DEPENDS_ON
    assert relations[1].relation_type == RelationType.ENABLES
    assert relations[2].relation_type == RelationType.RELATED_TO


def test_extract_relations_with_context(parser: MarkdownParser) -> None:
    """Test extracting relations with context."""
    content = """- depends_on [[redis-setup]] (for blacklist)
- enables [[api-gateway-auth]] (stateless design)
"""
    relations = parser.extract_relations(content)

    assert len(relations) == 2
    assert relations[0].context == "for blacklist"
    assert relations[1].context == "stateless design"


def test_extract_relations_with_path(parser: MarkdownParser) -> None:
    """Test extracting relations with path."""
    content = """- depends_on [[infrastructure/redis-setup]]
"""
    relations = parser.extract_relations(content)

    assert len(relations) == 1
    assert relations[0].target == "redis-setup"
    assert relations[0].target_path == "infrastructure"


def test_extract_relations_invalid_type(parser: MarkdownParser) -> None:
    """Test extracting relation with invalid type."""
    content = """- invalid_type [[target]]
"""
    with pytest.raises(InvalidRelationError):
        parser.extract_relations(content)


def test_extract_wikilinks_simple(parser: MarkdownParser) -> None:
    """Test extracting simple wikilinks."""
    content = """This references [[Note Title]] and [[Another Note]].
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Note Title"
    assert wikilinks[0].display_text is None
    assert wikilinks[1].target == "Another Note"


def test_extract_wikilinks_with_display(parser: MarkdownParser) -> None:
    """Test extracting wikilinks with display text."""
    content = """See [[Note Title|this note]] for details.
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 1
    assert wikilinks[0].target == "Note Title"
    assert wikilinks[0].display_text == "this note"


def test_extract_wikilinks_with_path(parser: MarkdownParser) -> None:
    """Test extracting wikilinks with path."""
    content = """See [[folder/Note Title]] for details.
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 1
    assert wikilinks[0].target == "Note Title"
    assert wikilinks[0].path == "folder"


def test_extract_headings(parser: MarkdownParser) -> None:
    """Test extracting headings."""
    content = """# Heading 1
## Heading 2
### Heading 3
#### Heading 4
##### Heading 5
###### Heading 6
"""
    headings = parser.extract_headings(content)

    assert len(headings) == 6
    assert headings[0] == (1, "Heading 1")
    assert headings[1] == (2, "Heading 2")
    assert headings[5] == (6, "Heading 6")


def test_generate_permalink(parser: MarkdownParser) -> None:
    """Test permalink generation."""
    assert parser.generate_permalink("Test Note") == "test-note"
    assert parser.generate_permalink("JWT Authentication") == "jwt-authentication"
    assert parser.generate_permalink("API v2.0") == "api-v20"
    assert parser.generate_permalink("Test---Note") == "test-note"
    assert parser.generate_permalink("  Test Note  ") == "test-note"
    assert parser.generate_permalink("") == "untitled"


def test_parse_full_note(parser: MarkdownParser) -> None:
    """Test parsing a complete note."""
    content = """---
title: Authentication JWT Implementation
type: decision
project: api-service
permalink: auth-jwt-impl
created: 2025-01-15T10:30:00Z
updated: 2025-01-16T14:20:00Z
tags:
  - security
  - backend
  - architecture
supersedes: auth-session-cookies
---

# Authentication JWT Implementation

## Context

Migrating from session-based to JWT authentication for API service.

- [decision] Chose JWT over session cookies for stateless API #architecture
- [reason] Horizontal scaling without shared session store #scalability
- [tradeoff] Tokens can't be revoked without blacklist #security

## Observations

- [implementation] Using RS256 with rotating keys #security (weekly rotation)
- [gotcha] Token refresh needs Redis for blacklist #infrastructure
- [pattern] Middleware validates on every request #performance
- [tip] Set short expiry (15min) with refresh tokens #security

## Relations

- depends_on [[redis-setup]]
- enables [[api-gateway-auth]]
- learned_from [[session-scaling-issues]]
- related_to [[user-authentication]]

## Session Log

### 2025-01-15 10:30

Implemented base JWT service with refresh tokens. Used python-jose library.

### 2025-01-16 09:00

Added key rotation mechanism. Keys stored in Vault.
"""
    note = parser.parse(content)

    assert note.frontmatter.title == "Authentication JWT Implementation"
    assert note.frontmatter.type == NoteType.DECISION
    assert len(note.observations) == 7
    assert len(note.relations) == 4
    assert len(note.wikilinks) == 4  # 4 from relations section
    assert len(note.headings) == 7  # 1 h1, 4 h2, 2 h3


def test_serialize_roundtrip(parser: MarkdownParser) -> None:
    """Test serializing and parsing back."""
    original = """---
title: Test Note
type: decision
tags:
  - test
---
# Test Note

Content here.
"""
    note = parser.parse(original)
    serialized = parser.serialize(note)
    note2 = parser.parse(serialized)

    assert note2.frontmatter.title == note.frontmatter.title
    assert note2.frontmatter.type == note.frontmatter.type
    assert note2.frontmatter.tags == note.frontmatter.tags


def test_update_frontmatter(parser: MarkdownParser) -> None:
    """Test updating frontmatter fields."""
    content = """---
title: Test Note
---
Content
"""
    updated = parser.update_frontmatter(
        content, {'updated': '2025-01-15T10:30:00Z'}
    )
    note = parser.parse(updated)

    assert note.frontmatter.title == "Test Note"
    assert note.frontmatter.updated is not None
