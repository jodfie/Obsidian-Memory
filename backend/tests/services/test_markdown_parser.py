"""Tests for MarkdownParser service."""

from datetime import datetime

import pytest

from app.models.note import (
    NoteType,
    ObservationCategory,
    RelationType,
)
from app.services.exceptions import FrontmatterError, InvalidObservationError
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
tags:
  - test
  - parser
---
# Test Note
Content here.
"""

    frontmatter_obj, remaining = parser.parse_frontmatter(content)

    assert frontmatter_obj.title == "Test Note"
    assert frontmatter_obj.type == NoteType.DECISION
    assert frontmatter_obj.project == "test-project"
    assert "test" in frontmatter_obj.tags
    assert "parser" in frontmatter_obj.tags
    assert "# Test Note" in remaining


def test_parse_frontmatter_missing_title(parser: MarkdownParser) -> None:
    """Test parsing frontmatter without title defaults to 'Untitled'."""
    content = """---
type: note
---
Content.
"""

    frontmatter_obj, _ = parser.parse_frontmatter(content)

    assert frontmatter_obj.title == "Untitled"
    assert frontmatter_obj.permalink is not None


def test_parse_frontmatter_extra_fields(parser: MarkdownParser) -> None:
    """Test that extra frontmatter fields are stored in extra dict."""
    content = """---
title: Test
custom_field: custom_value
another_field: 123
---
Content.
"""

    frontmatter_obj, _ = parser.parse_frontmatter(content)

    assert frontmatter_obj.extra["custom_field"] == "custom_value"
    assert frontmatter_obj.extra["another_field"] == 123


def test_parse_frontmatter_invalid_yaml(parser: MarkdownParser) -> None:
    """Test that invalid YAML raises FrontmatterError."""
    content = """---
title: Test
invalid: [unclosed
---
Content.
"""

    with pytest.raises(FrontmatterError):
        parser.parse_frontmatter(content)


def test_extract_observations_all_categories(parser: MarkdownParser) -> None:
    """Test extracting observations with all categories."""
    content = """- [decision] Chose option A
- [reason] Better performance
- [tradeoff] More complexity
- [implementation] Used library X
- [gotcha] Watch out for Y
- [pattern] Common pattern Z
- [tip] Always do this
- [fact] This is true
- [error] Something broke
- [solution] Fixed with X
- [experiment] Tried Y
- [resource] Link to docs
- [question] Why this?
- [answer] Because that
"""

    observations = parser.extract_observations(content)

    assert len(observations) == 14
    assert observations[0].category == ObservationCategory.DECISION
    assert observations[1].category == ObservationCategory.REASON
    assert observations[2].category == ObservationCategory.TRADEOFF


def test_extract_observations_with_tags(parser: MarkdownParser) -> None:
    """Test extracting observations with inline tags."""
    content = """- [tip] Always test #testing #best-practice
- [pattern] Use this pattern #architecture #scalability
"""

    observations = parser.extract_observations(content)

    assert len(observations) == 2
    assert "testing" in observations[0].tags
    assert "best-practice" in observations[0].tags
    assert "architecture" in observations[1].tags
    assert "scalability" in observations[1].tags


def test_extract_observations_with_context(parser: MarkdownParser) -> None:
    """Test extracting observations with context."""
    content = """- [gotcha] Watch for this #security (important)
- [tip] Do this #performance (benchmarked)
"""

    observations = parser.extract_observations(content)

    assert len(observations) == 2
    assert observations[0].context == "important"
    assert observations[1].context == "benchmarked"


def test_extract_observations_invalid_category(parser: MarkdownParser) -> None:
    """Test that invalid observation category raises error."""
    content = """- [invalid] This is invalid
"""

    with pytest.raises(InvalidObservationError):
        parser.extract_observations(content)


def test_extract_relations_all_types(parser: MarkdownParser) -> None:
    """Test extracting relations with all types."""
    content = """- depends_on [[Prerequisite]]
- enables [[Downstream]]
- related_to [[Other Note]]
- learned_from [[Source]]
- supersedes [[Old Note]]
- caused_by [[Root Cause]]
- solved_by [[Solution]]
- part_of [[Parent]]
- implements [[Spec]]
- tests [[Feature]]
- documents [[API]]
"""

    relations = parser.extract_relations(content)

    assert len(relations) == 11
    assert relations[0].relation_type == RelationType.DEPENDS_ON
    assert relations[0].target == "Prerequisite"
    assert relations[1].relation_type == RelationType.ENABLES
    assert relations[2].relation_type == RelationType.RELATED_TO


def test_extract_relations_with_context(parser: MarkdownParser) -> None:
    """Test extracting relations with context."""
    content = """- depends_on [[Prerequisite]] (required)
- enables [[Feature]] (optional)
"""

    relations = parser.extract_relations(content)

    assert len(relations) == 2
    assert relations[0].context == "required"
    assert relations[1].context == "optional"


def test_extract_relations_with_path(parser: MarkdownParser) -> None:
    """Test extracting relations with path in target."""
    content = """- depends_on [[folder/Note Title]]
"""

    relations = parser.extract_relations(content)

    assert len(relations) == 1
    assert relations[0].target == "Note Title"
    assert relations[0].target_path == "folder"


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
    content = """See [[Note Title|this link]] for more.
"""

    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 1
    assert wikilinks[0].target == "Note Title"
    assert wikilinks[0].display_text == "this link"


def test_extract_wikilinks_with_path(parser: MarkdownParser) -> None:
    """Test extracting wikilinks with path."""
    content = """See [[folder/Note Title]] and [[path/to/Another Note|display]].
"""

    wikilinks = parser.extract_wikilinks(content)

    assert len(wikilinks) == 2
    assert wikilinks[0].target == "Note Title"
    assert wikilinks[0].path == "folder"
    assert wikilinks[1].target == "Another Note"
    assert wikilinks[1].path == "path/to"
    assert wikilinks[1].display_text == "display"


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
    assert parser.generate_permalink("Test Title") == "test-title"
    assert parser.generate_permalink("Complex Title!") == "complex-title"
    assert parser.generate_permalink("  Multiple   Spaces  ") == "multiple-spaces"
    assert parser.generate_permalink("Special@Chars#Here") == "specialcharshere"
    assert parser.generate_permalink("") == "untitled"


def test_parse_full_note(parser: MarkdownParser) -> None:
    """Test parsing a complete note."""
    content = """---
title: Test Note
type: decision
project: test
---
# Test Note

- [decision] Chose option A #architecture
- [reason] Better performance #performance

- depends_on [[Prerequisite]]
- enables [[Feature]]

See [[Other Note]] for details.
"""

    note = parser.parse(content)

    assert note.frontmatter.title == "Test Note"
    assert note.frontmatter.type == NoteType.DECISION
    assert len(note.observations) == 2
    assert len(note.relations) == 2
    # Wikilinks include both relation targets and standalone wikilinks
    assert len(note.wikilinks) == 3
    assert len(note.headings) == 1


def test_serialize_roundtrip(parser: MarkdownParser) -> None:
    """Test serializing and parsing roundtrip."""
    original = """---
title: Original Title
type: note
---
# Original Title

Content here.
"""

    note = parser.parse(original)
    serialized = parser.serialize(note)
    reparsed = parser.parse(serialized)

    assert reparsed.frontmatter.title == note.frontmatter.title
    assert reparsed.frontmatter.type == note.frontmatter.type
    assert "# Original Title" in reparsed.raw_content


def test_update_frontmatter(parser: MarkdownParser) -> None:
    """Test updating frontmatter fields."""
    content = """---
title: Original
type: note
---
Content.
"""

    updated = parser.update_frontmatter(
        content, {"updated": "2025-01-15T10:00:00Z", "tags": ["new", "tag"]}
    )

    note = parser.parse(updated)
    assert note.frontmatter.updated is not None
    assert "new" in note.frontmatter.tags
    assert "tag" in note.frontmatter.tags


def test_parse_frontmatter_datetime(parser: MarkdownParser) -> None:
    """Test parsing datetime fields in frontmatter."""
    content = """---
title: Test
created: 2025-01-15T10:30:00Z
updated: 2025-01-16T14:20:00Z
---
Content.
"""

    frontmatter_obj, _ = parser.parse_frontmatter(content)

    assert frontmatter_obj.created is not None
    assert isinstance(frontmatter_obj.created, datetime)
    assert frontmatter_obj.updated is not None
    assert isinstance(frontmatter_obj.updated, datetime)


def test_parse_frontmatter_auto_permalink(parser: MarkdownParser) -> None:
    """Test that permalink is auto-generated from title."""
    content = """---
title: My Test Note
---
Content.
"""

    frontmatter_obj, _ = parser.parse_frontmatter(content)

    assert frontmatter_obj.permalink == "my-test-note"


def test_extract_observations_line_numbers(parser: MarkdownParser) -> None:
    """Test that observations track line numbers."""
    content = """Line 1
Line 2
- [tip] First observation
Line 4
- [fact] Second observation
"""

    observations = parser.extract_observations(content)

    assert observations[0].line_number == 3
    assert observations[1].line_number == 5


def test_extract_relations_line_numbers(parser: MarkdownParser) -> None:
    """Test that relations track line numbers."""
    content = """Line 1
- depends_on [[First]]
Line 3
- enables [[Second]]
"""

    relations = parser.extract_relations(content)

    assert relations[0].line_number == 2
    assert relations[1].line_number == 4
