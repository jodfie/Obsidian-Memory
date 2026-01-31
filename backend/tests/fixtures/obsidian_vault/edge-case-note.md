---
title:   Edge Case Note
type: note
tags:
  - test
  - edge-cases
extra_spacing:    value with spaces
---

# Edge Case Note

This note tests various edge cases:

## Trailing Whitespace

Lines with trailing spaces.
Another line.


## Multiple Blank Lines


Content after blank lines.


## Code Blocks with Markdown

```markdown
# Fake Heading

- [decision] Not a real observation
- depends_on [[Not A Real Link]]

[[Also Not Real]]
```

Regular [[Real Link]] outside code.

## Inline Code

Use `[[Not A Link]]` in inline code.

Pattern: `- [implementation] Not real` should be ignored.

## Mixed Content

- [question] How to handle edge cases? #testing
- [answer] Write comprehensive tests #solution

Normal wikilink: [[Other Note]]
With anchor: [[Note#Section]]
With block: [[Note#^block-id]]
With display: [[Note|Custom Text]]
With path: [[folder/Note]]

## Observations

- [error] Something went wrong #bug (in production)
- [solution] Fixed by restarting service #workaround


Final paragraph with blank lines below.


