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
    frontmatter, remaining, _ = parser.parse_frontmatter(content)

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
    frontmatter, _, _ = parser.parse_frontmatter(content)

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
    frontmatter, _, _ = parser.parse_frontmatter(content)

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


def test_wikilinks_skip_code_blocks(parser: MarkdownParser) -> None:
    """Test that wikilinks inside code blocks are not extracted."""
    content = """# Test

This is a normal [[Real Link]] here.

```python
# Example code with [[Not A Link]]
def foo():
    # Also [[Not A Link 2]]
    pass
```

Another normal [[Real Link 2]] after code.
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Real Link"
    assert wikilinks[1].target == "Real Link 2"


def test_wikilinks_skip_inline_code(parser: MarkdownParser) -> None:
    """Test that wikilinks inside inline code are not extracted."""
    content = """# Test

This is `[[Not A Link]]` in inline code.

This is a real [[Actual Link]] here.

Use function `call_api([[param]])` with backticks.
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 1
    assert wikilinks[0].target == "Actual Link"


def test_observations_skip_code_blocks(parser: MarkdownParser) -> None:
    """Test that observations inside code blocks are not extracted."""
    content = """# Test

- [decision] Real observation

```markdown
# Example markdown
- [decision] Not a real observation
- [reason] Also not real
```

- [implementation] Another real one
"""
    observations = parser.extract_observations(content)

    assert len(observations) == 2
    assert observations[0].category == ObservationCategory.DECISION
    assert observations[0].content == "Real observation"
    assert observations[1].category == ObservationCategory.IMPLEMENTATION
    assert observations[1].content == "Another real one"


def test_observations_skip_inline_code(parser: MarkdownParser) -> None:
    """Test that observations inside inline code are not extracted."""
    content = """# Test

Example pattern: `- [decision] Not real`

- [decision] This is real

The pattern `- [implementation] Also not real` should be ignored.
"""
    observations = parser.extract_observations(content)

    assert len(observations) == 1
    assert observations[0].content == "This is real"


def test_relations_skip_code_blocks(parser: MarkdownParser) -> None:
    """Test that relations inside code blocks are not extracted."""
    content = """# Test

- depends_on [[Real Dependency]]

```
Example relations:
- depends_on [[Not Real]]
- enables [[Also Not Real]]
```

- enables [[Real Enabled]]
"""
    relations = parser.extract_relations(content)

    assert len(relations) == 2
    assert relations[0].relation_type == RelationType.DEPENDS_ON
    assert relations[0].target == "Real Dependency"
    assert relations[1].relation_type == RelationType.ENABLES
    assert relations[1].target == "Real Enabled"


def test_code_block_adjacent_to_wikilinks(parser: MarkdownParser) -> None:
    """Test that wikilinks adjacent to code blocks are still extracted."""
    content = """Before [[Link Before]]
```
code block
```
After [[Link After]]
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Link Before"
    assert wikilinks[1].target == "Link After"


def test_nested_code_blocks(parser: MarkdownParser) -> None:
    """Test handling of nested code block markers."""
    content = """# Test

```markdown
This is markdown code containing:
```python
nested_code()
```
back to markdown
```

Normal [[Link]] here.
"""
    wikilinks = parser.extract_wikilinks(content)

    # The nested ``` should close the first block, and another ``` opens a new one
    # So we have: open(1) -> close(4) -> open(5) -> close(6)
    # Line 9 "Normal [[Link]]" should be extracted
    assert len(wikilinks) == 1
    assert wikilinks[0].target == "Link"


def test_unclosed_code_block(parser: MarkdownParser) -> None:
    """Test handling of unclosed code blocks."""
    content = """# Test

Normal [[Link 1]] before code.

```python
# Code starts here
def foo():
    # [[Not A Link]] in unclosed block
    pass

# More code
# [[Another Non-Link]]
"""
    wikilinks = parser.extract_wikilinks(content)

    # Only the link before the unclosed code block should be extracted
    assert len(wikilinks) == 1
    assert wikilinks[0].target == "Link 1"


def test_multiple_code_blocks(parser: MarkdownParser) -> None:
    """Test multiple separate code blocks."""
    content = """# Test

[[Link 1]]

```
code block 1
[[Not Link 1]]
```

[[Link 2]]

```
code block 2
[[Not Link 2]]
```

[[Link 3]]
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 3
    targets = [link.target for link in wikilinks]
    assert targets == ["Link 1", "Link 2", "Link 3"]


def test_wikilink_with_heading_anchor(parser: MarkdownParser) -> None:
    """Test extracting wikilinks with heading anchors."""
    content = """# Test

See [[Note#Introduction]] for background.

Also check [[Another Note#Configuration|config docs]].
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Note"
    assert wikilinks[0].anchor == "Introduction"
    assert wikilinks[0].block_ref is None
    assert wikilinks[0].display_text is None

    assert wikilinks[1].target == "Another Note"
    assert wikilinks[1].anchor == "Configuration"
    assert wikilinks[1].block_ref is None
    assert wikilinks[1].display_text == "config docs"


def test_wikilink_with_block_reference(parser: MarkdownParser) -> None:
    """Test extracting wikilinks with block references."""
    content = """# Test

Quote from [[Note#^blockid123]] here.

Also see [[Another#^abc-def-456|this specific block]].
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Note"
    assert wikilinks[0].anchor is None
    assert wikilinks[0].block_ref == "blockid123"
    assert wikilinks[0].display_text is None

    assert wikilinks[1].target == "Another"
    assert wikilinks[1].anchor is None
    assert wikilinks[1].block_ref == "abc-def-456"
    assert wikilinks[1].display_text == "this specific block"


def test_wikilink_with_anchor_and_display(parser: MarkdownParser) -> None:
    """Test wikilinks with both anchor and display text."""
    content = """# Test

See [[Note#Section|custom display]] for details.

Also [[Guide#Getting Started|start here]].
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Note"
    assert wikilinks[0].anchor == "Section"
    assert wikilinks[0].display_text == "custom display"

    assert wikilinks[1].target == "Guide"
    assert wikilinks[1].anchor == "Getting Started"
    assert wikilinks[1].display_text == "start here"


def test_wikilink_without_anchor(parser: MarkdownParser) -> None:
    """Test that regular wikilinks still work without anchors."""
    content = """# Test

Regular [[Simple Link]] here.

Also [[Another Link|with display]].

And [[folder/Nested Link]].
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 3

    # Regular link
    assert wikilinks[0].target == "Simple Link"
    assert wikilinks[0].anchor is None
    assert wikilinks[0].block_ref is None
    assert wikilinks[0].display_text is None

    # With display
    assert wikilinks[1].target == "Another Link"
    assert wikilinks[1].anchor is None
    assert wikilinks[1].block_ref is None
    assert wikilinks[1].display_text == "with display"

    # With path
    assert wikilinks[2].target == "Nested Link"
    assert wikilinks[2].path == "folder"
    assert wikilinks[2].anchor is None
    assert wikilinks[2].block_ref is None


def test_wikilink_anchor_in_code_block(parser: MarkdownParser) -> None:
    """Test that anchors in code blocks are not extracted."""
    content = """# Test

Real [[Note#Section]] link.

```
Example: [[Note#FakeSection]]
Block ref: [[Note#^fakeblock]]
```

Another real [[Doc#Introduction]] link.
"""
    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Note"
    assert wikilinks[0].anchor == "Section"

    assert wikilinks[1].target == "Doc"
    assert wikilinks[1].anchor == "Introduction"


def test_roundtrip_byte_identical(parser: MarkdownParser) -> None:
    """Test that parsing and serializing produces byte-identical output."""
    original = """---
title: Test Note
type: decision
project: test-project
tags:
  - test
  - parser
---
# Test Note

Content here with **bold** and *italic*.

- [decision] Some decision
- related_to [[Other Note]]

More content.
"""
    note = parser.parse(original)
    serialized = parser.serialize(note)

    assert serialized == original


def test_roundtrip_preserves_trailing_whitespace(parser: MarkdownParser) -> None:
    """Test that trailing whitespace in content is preserved."""
    original = """---
title: Test
---
Line with trailing spaces
Another line
Normal line
"""
    note = parser.parse(original)
    serialized = parser.serialize(note)

    assert serialized == original


def test_roundtrip_preserves_blank_lines(parser: MarkdownParser) -> None:
    """Test that blank line patterns are preserved."""
    original = """---
title: Test
---
# Heading


Content with multiple blank lines above.


And below.


"""
    note = parser.parse(original)
    serialized = parser.serialize(note)

    assert serialized == original


def test_roundtrip_preserves_frontmatter_formatting(parser: MarkdownParser) -> None:
    """Test that frontmatter YAML formatting is preserved exactly."""
    original = """---
title:   Test Note
type: decision
tags:
  - first
  - second
project:    my-project
---
Content
"""
    note = parser.parse(original)
    serialized = parser.serialize(note)

    assert serialized == original


def test_roundtrip_modified_frontmatter_regenerates(parser: MarkdownParser) -> None:
    """Test that modified frontmatter is regenerated, not preserved."""
    original = """---
title: Original Title
type: note
---
Content here.
"""
    note = parser.parse(original)

    # Modify frontmatter
    note.frontmatter.title = "New Title"
    note.frontmatter_modified = True

    serialized = parser.serialize(note)

    # Should have new title in regenerated frontmatter
    assert "title: New Title" in serialized
    assert "Original Title" not in serialized
    assert "Content here." in serialized


def test_roundtrip_preserves_complex_content(parser: MarkdownParser) -> None:
    """Test round-trip with complex real-world content."""
    original = """---
title: Complex Note
type: decision
project: api-service
permalink: complex-note
created: 2025-01-15T10:30:00Z
updated: 2025-01-16T14:20:00Z
tags:
  - test
  - complex
custom_field: custom value
---
# Complex Note

## Section 1

Some content with [[Wikilink]] and [[Another|display]].

- [decision] Made a choice #tag1 #tag2
- [implementation] Did something (with context)
- depends_on [[Dependency]]

```python
# Code block with [[Not A Link]]
def foo():
    pass
```

## Section 2

More content with trailing spaces
And blank lines below.


Final paragraph.
"""
    note = parser.parse(original)
    serialized = parser.serialize(note)

    assert serialized == original


def test_roundtrip_without_frontmatter(parser: MarkdownParser) -> None:
    """Test round-trip for content without frontmatter."""
    original = """# Just Content

No frontmatter here.
"""
    note = parser.parse(original)
    serialized = parser.serialize(note)

    # Without frontmatter, we'll get a generated one
    # Just verify content is preserved
    assert "# Just Content" in serialized
    assert "No frontmatter here." in serialized
