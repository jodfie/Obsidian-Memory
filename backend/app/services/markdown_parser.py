"""Markdown parser for Obsidian-compatible markdown files."""

import re
from datetime import datetime
from typing import Any

import frontmatter
import yaml

from app.models.note import (
    Frontmatter,
    NoteType,
    Observation,
    ObservationCategory,
    ParsedNote,
    Relation,
    RelationType,
    Wikilink,
)
from app.services.exceptions import (
    FrontmatterError,
    InvalidObservationError,
    InvalidRelationError,
    ParseError,
)


# Regex patterns
FRONTMATTER_PATTERN = re.compile(
    r'^---\s*\n(.*?)\n---\s*\n',
    re.DOTALL | re.MULTILINE
)

OBSERVATION_PATTERN = re.compile(
    r'^-\s*\[(\w+)\]\s*(.+?)(?:\s*\(([^)]+)\))?\s*$',
    re.MULTILINE
)

RELATION_PATTERN = re.compile(
    r'^-\s*(\w+)\s+\[\[([^\]|]+)(?:\|[^\]]+)?\]\](?:\s*\(([^)]+)\))?\s*$',
    re.MULTILINE
)

WIKILINK_PATTERN = re.compile(
    r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'
)

HEADING_PATTERN = re.compile(
    r'^(#{1,6})\s+(.+)$',
    re.MULTILINE
)

INLINE_TAG_PATTERN = re.compile(
    r'(?<!\S)#([\w-]+)(?!\S)'
)


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
        # Parse frontmatter
        frontmatter_obj, raw_content = self.parse_frontmatter(content)

        # Extract all structured data
        observations = self.extract_observations(raw_content)
        relations = self.extract_relations(raw_content)
        wikilinks = self.extract_wikilinks(raw_content)
        headings = self.extract_headings(raw_content)

        return ParsedNote(
            frontmatter=frontmatter_obj,
            observations=observations,
            relations=relations,
            wikilinks=wikilinks,
            raw_content=raw_content,
            headings=headings,
        )

    def parse_frontmatter(self, content: str) -> tuple[Frontmatter, str]:
        """
        Extract and parse YAML frontmatter.

        Args:
            content: Raw markdown content

        Returns:
            Tuple of (parsed frontmatter, remaining content)

        Raises:
            FrontmatterError: If YAML is malformed
        """
        try:
            post = frontmatter.loads(content)
        except Exception as e:
            raise FrontmatterError(f"Invalid YAML frontmatter: {e}") from e

        # Extract known fields, put rest in extra
        known_fields = {
            'title',
            'type',
            'project',
            'permalink',
            'created',
            'updated',
            'tags',
            'supersedes',
            'superseded_by',
        }
        extra = {
            k: v for k, v in post.metadata.items() if k not in known_fields
        }

        # Auto-generate permalink if missing
        permalink = post.metadata.get('permalink')
        if not permalink:
            title = post.metadata.get('title', 'Untitled')
            permalink = self.generate_permalink(title)

        # Parse datetime fields
        created = post.metadata.get('created')
        if created and isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace('Z', '+00:00'))
            except ValueError:
                created = None

        updated = post.metadata.get('updated')
        if updated and isinstance(updated, str):
            try:
                updated = datetime.fromisoformat(updated.replace('Z', '+00:00'))
            except ValueError:
                updated = None

        # Parse note type
        note_type = NoteType.NOTE
        if 'type' in post.metadata:
            try:
                note_type = NoteType(post.metadata['type'])
            except ValueError:
                note_type = NoteType.NOTE

        # Ensure tags is a list
        tags = post.metadata.get('tags', [])
        if not isinstance(tags, list):
            tags = [tags] if tags else []

        frontmatter_obj = Frontmatter(
            title=post.metadata.get('title', 'Untitled'),
            type=note_type,
            project=post.metadata.get('project'),
            permalink=permalink,
            created=created,
            updated=updated,
            tags=tags,
            supersedes=post.metadata.get('supersedes'),
            superseded_by=post.metadata.get('superseded_by'),
            extra=extra,
        )

        return frontmatter_obj, post.content

    def extract_observations(self, content: str) -> list[Observation]:
        """
        Extract all observations from content.

        Matches pattern: - [category] content #tags (context)
        """
        observations: list[Observation] = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            match = OBSERVATION_PATTERN.match(line.strip())
            if match:
                category_str = match.group(1).lower()
                content_text = match.group(2).strip()
                context = match.group(3)

                # Validate category
                try:
                    category = ObservationCategory(category_str)
                except ValueError:
                    raise InvalidObservationError(
                        f"Invalid observation category: {category_str}",
                        line_number=line_num,
                    )

                # Parse inline tags from content
                tags = self._parse_inline_tags(content_text)
                # Remove all tags from content
                content_text = INLINE_TAG_PATTERN.sub('', content_text)
                # Clean up extra spaces
                content_text = re.sub(r'\s+', ' ', content_text).strip()

                observations.append(
                    Observation(
                        category=category,
                        content=content_text,
                        tags=tags,
                        context=context,
                        line_number=line_num,
                    )
                )

        return observations

    def extract_relations(self, content: str) -> list[Relation]:
        """
        Extract all semantic relations from content.

        Matches pattern: - relation_type [[Target]]
        """
        relations: list[Relation] = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            match = RELATION_PATTERN.match(line.strip())
            if match:
                relation_type_str = match.group(1).lower()
                target = match.group(2).strip()
                context = match.group(3)

                # Validate relation type
                try:
                    relation_type = RelationType(relation_type_str)
                except ValueError:
                    raise InvalidRelationError(
                        f"Invalid relation type: {relation_type_str}",
                        line_number=line_num,
                    )

                # Parse target path if present
                target_path = None
                if '/' in target:
                    parts = target.rsplit('/', 1)
                    if len(parts) == 2:
                        target_path = parts[0]
                        target = parts[1]

                relations.append(
                    Relation(
                        relation_type=relation_type,
                        target=target,
                        target_path=target_path,
                        context=context,
                        line_number=line_num,
                    )
                )

        return relations

    def extract_wikilinks(self, content: str) -> list[Wikilink]:
        """
        Extract all wikilinks from content.

        Matches patterns:
        - [[Note Title]]
        - [[Note Title|Display]]
        - [[folder/Note Title]]
        """
        wikilinks: list[Wikilink] = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, start=1):
            for match in WIKILINK_PATTERN.finditer(line):
                target = match.group(1).strip()
                display_text = match.group(2)

                # Parse path if present
                path = None
                if '/' in target:
                    parts = target.rsplit('/', 1)
                    if len(parts) == 2:
                        path = parts[0]
                        target = parts[1]

                column = match.start()

                wikilinks.append(
                    Wikilink(
                        target=target,
                        display_text=display_text,
                        path=path,
                        line_number=line_num,
                        column=column,
                    )
                )

        return wikilinks

    def extract_headings(self, content: str) -> list[tuple[int, str]]:
        """
        Extract all markdown headings.

        Returns list of (level, text) where level is 1-6.
        """
        headings: list[tuple[int, str]] = []
        for match in HEADING_PATTERN.finditer(content):
            level = len(match.group(1))
            text = match.group(2).strip()
            headings.append((level, text))
        return headings

    def generate_permalink(self, title: str) -> str:
        """
        Generate URL-safe permalink from title.

        Rules:
        - Lowercase
        - Replace spaces with hyphens
        - Remove special characters except hyphens
        - Collapse multiple hyphens
        """
        # Lowercase
        permalink = title.lower()

        # Replace spaces and underscores with hyphens
        permalink = re.sub(r'[\s_]+', '-', permalink)

        # Remove special characters except hyphens
        permalink = re.sub(r'[^a-z0-9-]', '', permalink)

        # Collapse multiple hyphens
        permalink = re.sub(r'-+', '-', permalink)

        # Remove leading/trailing hyphens
        permalink = permalink.strip('-')

        return permalink or 'untitled'

    def serialize(self, note: ParsedNote) -> str:
        """
        Serialize ParsedNote back to markdown.

        Preserves original content structure while updating
        frontmatter with any changes.
        """
        # Build frontmatter dict
        metadata: dict[str, Any] = {
            'title': note.frontmatter.title,
            'type': note.frontmatter.type.value,
        }

        if note.frontmatter.project:
            metadata['project'] = note.frontmatter.project
        if note.frontmatter.permalink:
            metadata['permalink'] = note.frontmatter.permalink
        if note.frontmatter.created:
            metadata['created'] = note.frontmatter.created.isoformat()
        if note.frontmatter.updated:
            metadata['updated'] = note.frontmatter.updated.isoformat()
        if note.frontmatter.tags:
            metadata['tags'] = note.frontmatter.tags
        if note.frontmatter.supersedes:
            metadata['supersedes'] = note.frontmatter.supersedes
        if note.frontmatter.superseded_by:
            metadata['superseded_by'] = note.frontmatter.superseded_by

        # Add extra fields
        metadata.update(note.frontmatter.extra)

        # Create frontmatter post
        post = frontmatter.Post(note.raw_content, **metadata)

        return frontmatter.dumps(post)

    def update_frontmatter(self, content: str, updates: dict[str, Any]) -> str:
        """
        Update frontmatter fields without reparsing entire note.

        Useful for updating 'updated' timestamp on edits.
        """
        try:
            post = frontmatter.loads(content)
        except Exception as e:
            raise FrontmatterError(f"Invalid YAML frontmatter: {e}") from e

        # Update fields
        post.metadata.update(updates)

        return frontmatter.dumps(post)

    def _parse_inline_tags(self, tags_str: str) -> list[str]:
        """Parse inline tags from string like '#tag1 #tag2'."""
        if not tags_str:
            return []

        tags: list[str] = []
        for match in INLINE_TAG_PATTERN.finditer(tags_str):
            tags.append(match.group(1))

        return tags
