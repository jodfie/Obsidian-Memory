"""Utility for stripping injected memory context blocks from content.

Prevents feedback loops where injected context gets re-stored as new memories.
Uses HTML comment markers that are invisible in rendered markdown/HTML output.
"""

import re

# Standard markers for injected memory context blocks
CONTEXT_BLOCK_START = "<!-- memory-context-start -->"
CONTEXT_BLOCK_END = "<!-- memory-context-end -->"

# Compiled regex: non-greedy match between start/end markers (spans newlines)
CONTEXT_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    re.escape(CONTEXT_BLOCK_START) + r".*?" + re.escape(CONTEXT_BLOCK_END),
    re.DOTALL,
)

# Minimum content length after stripping to be worth storing
MIN_CONTENT_LENGTH = 10


def strip_injected_context(content: str) -> str:
    """Remove all injected memory context blocks from content.

    Args:
        content: Raw content that may contain injected context blocks.

    Returns:
        Content with all context blocks removed and whitespace normalized.
        Returns empty string if input is empty/None-ish.
    """
    if not content:
        return content or ""

    stripped = CONTEXT_BLOCK_PATTERN.sub("", content)

    # Normalize excessive newlines left by removal
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)

    return stripped.strip()


def has_meaningful_content(content: str) -> bool:
    """Check if content has enough meaningful text after stripping context blocks.

    Args:
        content: Raw content (context blocks will be stripped first).

    Returns:
        True if stripped content has >= MIN_CONTENT_LENGTH characters.
    """
    stripped = strip_injected_context(content)
    return len(stripped) >= MIN_CONTENT_LENGTH
