# Markdown Parser Specification

## Overview

The Markdown Parser extracts structured data from Obsidian-compatible markdown files including YAML frontmatter, observations, relations, and wikilinks.

## Scope

This spec covers ONLY parsing markdown into structured data. It does NOT cover:
- File I/O (see `core-vault-manager.md`)
- Indexing parsed data (see `core-search-index.md`)
- Graph construction (see `graph-engine.md`)

## Markdown Format

### Complete Example

```markdown
---
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
```

### Frontmatter Schema

Required fields:
- `title` (string): Note title

Optional fields:
- `type` (string): Note type - one of: `note`, `decision`, `error`, `knowledge`, `pattern`, `session`, `research`
- `project` (string): Project identifier
- `permalink` (string): URL-safe slug for linking (auto-generated from title if missing)
- `created` (ISO datetime): Creation timestamp
- `updated` (ISO datetime): Last update timestamp
- `tags` (list[string]): Categorization tags
- `supersedes` (string): Permalink of note this replaces
- `superseded_by` (string): Permalink of note that replaced this

### Observation Format

```
- [category] content #tag1 #tag2 (context)
```

Components:
- `[category]` - Required. One of: `decision`, `reason`, `tradeoff`, `implementation`, `gotcha`, `pattern`, `tip`, `fact`, `error`, `solution`, `experiment`, `resource`, `question`, `answer`
- `content` - Required. The observation text
- `#tag` - Optional. Inline tags (multiple allowed)
- `(context)` - Optional. Additional context in parentheses

### Relation Format

```
- relation_type [[Target Note]]
- relation_type [[Target Note]] (context)
```

Relation types:
- `depends_on` - Prerequisite relationship
- `enables` - This enables the target
- `related_to` - General relation
- `learned_from` - Knowledge derived from
- `supersedes` - Replaces older note
- `caused_by` - Error/issue causation
- `solved_by` - Problem solution link
- `part_of` - Hierarchical membership
- `implements` - Implements a spec/design
- `tests` - Tests the target
- `documents` - Documentation link

### Wikilink Format

```
[[Note Title]]
[[Note Title|Display Text]]
[[folder/Note Title]]
```

## Data Structures

### ParsedNote

```python
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class NoteType(str, Enum):
    NOTE = "note"
    DECISION = "decision"
    ERROR = "error"
    KNOWLEDGE = "knowledge"
    PATTERN = "pattern"
    SESSION = "session"
    RESEARCH = "research"

class ObservationCategory(str, Enum):
    DECISION = "decision"
    REASON = "reason"
    TRADEOFF = "tradeoff"
    IMPLEMENTATION = "implementation"
    GOTCHA = "gotcha"
    PATTERN = "pattern"
    TIP = "tip"
    FACT = "fact"
    ERROR = "error"
    SOLUTION = "solution"
    EXPERIMENT = "experiment"
    RESOURCE = "resource"
    QUESTION = "question"
    ANSWER = "answer"

class RelationType(str, Enum):
    DEPENDS_ON = "depends_on"
    ENABLES = "enables"
    RELATED_TO = "related_to"
    LEARNED_FROM = "learned_from"
    SUPERSEDES = "supersedes"
    CAUSED_BY = "caused_by"
    SOLVED_BY = "solved_by"
    PART_OF = "part_of"
    IMPLEMENTS = "implements"
    TESTS = "tests"
    DOCUMENTS = "documents"

class Frontmatter(BaseModel):
    """Parsed YAML frontmatter."""
    title: str
    type: NoteType = NoteType.NOTE
    project: str | None = None
    permalink: str | None = None  # Auto-generated if missing
    created: datetime | None = None
    updated: datetime | None = None
    tags: list[str] = []
    supersedes: str | None = None
    superseded_by: str | None = None
    extra: dict = {}  # Any additional frontmatter fields

class Observation(BaseModel):
    """A structured observation from note content."""
    category: ObservationCategory
    content: str
    tags: list[str] = []
    context: str | None = None
    line_number: int  # For error reporting

class Relation(BaseModel):
    """A semantic relation to another note."""
    relation_type: RelationType
    target: str  # Target note title/permalink
    target_path: str | None = None  # Resolved path if wikilink had path
    context: str | None = None
    line_number: int

class Wikilink(BaseModel):
    """A wikilink reference."""
    target: str  # The linked note title
    display_text: str | None = None  # Optional display text
    path: str | None = None  # Optional folder path
    line_number: int
    column: int  # Character position in line

class ParsedNote(BaseModel):
    """Fully parsed note structure."""
    frontmatter: Frontmatter
    observations: list[Observation] = []
    relations: list[Relation] = []
    wikilinks: list[Wikilink] = []
    raw_content: str  # Original content without frontmatter
    headings: list[tuple[int, str]] = []  # (level, text) pairs
```

## Interface

### MarkdownParser Class

```python
class MarkdownParser:
    """Parses Obsidian-compatible markdown files."""

    def parse(self, content: str) -> ParsedNote:
        """
        Parse markdown content into structured data.

        Args:
            content: Raw markdown file content

        Returns:
            ParsedNote with all extracted structure

        Raises:
            ParseError: If frontmatter is invalid YAML
        """

    def parse_frontmatter(self, content: str) -> tuple[Frontmatter, str]:
        """
        Extract and parse YAML frontmatter.

        Args:
            content: Raw markdown content

        Returns:
            Tuple of (parsed frontmatter, remaining content)

        Raises:
            ParseError: If YAML is malformed
        """

    def extract_observations(self, content: str) -> list[Observation]:
        """
        Extract all observations from content.

        Matches pattern: - [category] content #tags (context)
        """

    def extract_relations(self, content: str) -> list[Relation]:
        """
        Extract all semantic relations from content.

        Matches pattern: - relation_type [[Target]]
        """

    def extract_wikilinks(self, content: str) -> list[Wikilink]:
        """
        Extract all wikilinks from content.

        Matches patterns:
        - [[Note Title]]
        - [[Note Title|Display]]
        - [[folder/Note Title]]
        """

    def extract_headings(self, content: str) -> list[tuple[int, str]]:
        """
        Extract all markdown headings.

        Returns list of (level, text) where level is 1-6.
        """

    def generate_permalink(self, title: str) -> str:
        """
        Generate URL-safe permalink from title.

        Rules:
        - Lowercase
        - Replace spaces with hyphens
        - Remove special characters except hyphens
        - Collapse multiple hyphens
        """

    # Serialization
    def serialize(self, note: ParsedNote) -> str:
        """
        Serialize ParsedNote back to markdown.

        Preserves original content structure while updating
        frontmatter with any changes.
        """

    def update_frontmatter(self, content: str, updates: dict) -> str:
        """
        Update frontmatter fields without reparsing entire note.

        Useful for updating 'updated' timestamp on edits.
        """
```

## Regex Patterns

```python
import re

# Frontmatter: starts with ---, ends with ---
FRONTMATTER_PATTERN = re.compile(
    r'^---\s*\n(.*?)\n---\s*\n',
    re.DOTALL
)

# Observation: - [category] content #tags (context)
OBSERVATION_PATTERN = re.compile(
    r'^-\s*\[(\w+)\]\s*(.+?)(?:\s+((?:#\w+\s*)+))?(?:\s*\(([^)]+)\))?\s*$',
    re.MULTILINE
)

# Relation: - relation_type [[Target]] (context)
RELATION_PATTERN = re.compile(
    r'^-\s*(\w+)\s+\[\[([^\]|]+)(?:\|[^\]]+)?\]\](?:\s*\(([^)]+)\))?\s*$',
    re.MULTILINE
)

# Wikilink: [[target]] or [[target|display]] or [[path/target]]
WIKILINK_PATTERN = re.compile(
    r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'
)

# Heading: # to ###### followed by text
HEADING_PATTERN = re.compile(
    r'^(#{1,6})\s+(.+)$',
    re.MULTILINE
)

# Inline tag: #word (not in code blocks)
INLINE_TAG_PATTERN = re.compile(
    r'(?<!\S)#(\w+)(?!\S)'
)
```

## Error Handling

```python
class ParseError(Exception):
    """Base parsing error."""
    def __init__(self, message: str, line_number: int | None = None):
        self.line_number = line_number
        super().__init__(f"Line {line_number}: {message}" if line_number else message)

class FrontmatterError(ParseError):
    """Invalid YAML frontmatter."""

class InvalidObservationError(ParseError):
    """Observation doesn't match expected format."""

class InvalidRelationError(ParseError):
    """Relation doesn't match expected format."""
```

## Implementation Notes

### Frontmatter Parsing

Use `python-frontmatter` library for robust YAML handling:

```python
import frontmatter

def parse_frontmatter(self, content: str) -> tuple[Frontmatter, str]:
    post = frontmatter.loads(content)

    # Extract known fields, put rest in extra
    known_fields = {'title', 'type', 'project', 'permalink', 'created', 'updated', 'tags', 'supersedes', 'superseded_by'}
    extra = {k: v for k, v in post.metadata.items() if k not in known_fields}

    # Auto-generate permalink if missing
    permalink = post.metadata.get('permalink')
    if not permalink and 'title' in post.metadata:
        permalink = self.generate_permalink(post.metadata['title'])

    return Frontmatter(
        title=post.metadata.get('title', 'Untitled'),
        type=post.metadata.get('type', 'note'),
        # ... other fields
        extra=extra
    ), post.content
```

### Line Number Tracking

Track line numbers for observations/relations for error reporting:

```python
def extract_observations(self, content: str) -> list[Observation]:
    observations = []
    for line_num, line in enumerate(content.split('\n'), start=1):
        match = OBSERVATION_PATTERN.match(line)
        if match:
            observations.append(Observation(
                category=match.group(1),
                content=match.group(2),
                tags=self._parse_inline_tags(match.group(3) or ''),
                context=match.group(4),
                line_number=line_num
            ))
    return observations
```

### Wikilink Resolution

Wikilinks can be:
- Simple: `[[Note Title]]` → target="Note Title"
- With display: `[[Note Title|Display]]` → target="Note Title", display_text="Display"
- With path: `[[folder/Note Title]]` → target="Note Title", path="folder"

## File Location

```
backend/
└── app/
    └── services/
        └── markdown_parser.py
```

## Tests Required

```
backend/tests/
└── services/
    └── test_markdown_parser.py
        ├── test_parse_frontmatter_valid
        ├── test_parse_frontmatter_missing_title
        ├── test_parse_frontmatter_extra_fields
        ├── test_parse_frontmatter_invalid_yaml
        ├── test_extract_observations_all_categories
        ├── test_extract_observations_with_tags
        ├── test_extract_observations_with_context
        ├── test_extract_relations_all_types
        ├── test_extract_relations_with_context
        ├── test_extract_wikilinks_simple
        ├── test_extract_wikilinks_with_display
        ├── test_extract_wikilinks_with_path
        ├── test_extract_headings
        ├── test_generate_permalink
        ├── test_serialize_roundtrip
        └── test_update_frontmatter
```

## Dependencies

- `python-frontmatter` - YAML frontmatter parsing
- `pydantic` - Data validation
- `pyyaml` - YAML serialization
