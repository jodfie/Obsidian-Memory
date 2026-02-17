"""Decay auto-classification and expiry calculation.

Classifies notes into five decay tiers based on priority rules:
  1. Explicit frontmatter override (highest)
  2. Note type mapping
  3. Tag-based rules
  4. Content pattern matching
  5. Default: 'stable'
"""

import re
from datetime import datetime, timedelta
from typing import Literal

DecayClass = Literal['permanent', 'stable', 'active', 'session', 'checkpoint']

# TTL values in seconds (None = never expires)
DECAY_TTL: dict[str, int | None] = {
    'permanent': None,
    'stable': 90 * 24 * 3600,      # 90 days
    'active': 14 * 24 * 3600,      # 14 days
    'session': 24 * 3600,           # 24 hours
    'checkpoint': 4 * 3600,         # 4 hours
}

VALID_DECAY_CLASSES = frozenset(DECAY_TTL.keys())

# --- Compiled patterns at module level for performance ---

PERMANENT_PATTERNS = re.compile(
    r'(?:decided|chose|picked|selected|choosing)\s+(?:to\s+)?(?:use\s+)?'
    r'|(?:always|never|must|should always|should never)\s+'
    r'|(?:went with|sticking with|going with)\s+'
    r'|(?:convention|architecture)',
    re.IGNORECASE,
)

ACTIVE_PATTERNS = re.compile(
    r'(?:working on|todo|blocker|need to|blocked by|in progress|wip)',
    re.IGNORECASE,
)

SESSION_PATTERNS = re.compile(
    r'(?:currently debugging|right now|this session|temporary fix|debug this|temp)',
    re.IGNORECASE,
)

# --- Tag sets for classification ---

PERMANENT_TAGS = frozenset({'permanent', 'architecture', 'convention'})
CHECKPOINT_TAGS = frozenset({'checkpoint', 'preflight'})
SESSION_TAGS = frozenset({'debug', 'temp', 'temporary'})
ACTIVE_TAGS = frozenset({'wip', 'sprint', 'task', 'todo'})

# --- Note type → decay class mapping ---

NOTE_TYPE_DECAY: dict[str, DecayClass] = {
    'decision': 'permanent',
    'session': 'session',
    'error': 'active',
}


def classify_decay(
    note_type: str,
    tags: list[str],
    frontmatter: dict,
    content: str,
) -> DecayClass:
    """Classify note decay based on priority rules.

    Args:
        note_type: The note's type (decision, session, error, etc.)
        tags: List of tags from frontmatter
        frontmatter: Extra frontmatter dict (may contain decay_class override)
        content: Full note body text

    Returns:
        The appropriate DecayClass for this note.
    """
    # 1. Explicit frontmatter override (highest priority)
    if 'decay_class' in frontmatter:
        decay = frontmatter['decay_class']
        if decay in VALID_DECAY_CLASSES:
            return decay

    # 2. Note type mapping
    if note_type in NOTE_TYPE_DECAY:
        return NOTE_TYPE_DECAY[note_type]

    # 3. Tag-based rules (normalize: lowercase, strip leading #)
    tag_set = {t.lower().lstrip('#') for t in tags}

    if tag_set & PERMANENT_TAGS:
        return 'permanent'
    if tag_set & CHECKPOINT_TAGS:
        return 'checkpoint'
    if tag_set & SESSION_TAGS:
        return 'session'
    if tag_set & ACTIVE_TAGS:
        return 'active'

    # 4. Content pattern matching
    if PERMANENT_PATTERNS.search(content):
        return 'permanent'
    if SESSION_PATTERNS.search(content):
        return 'session'
    if ACTIVE_PATTERNS.search(content):
        return 'active'

    # 5. Default
    return 'stable'


def calculate_expiry(
    decay_class: DecayClass,
    base_time: datetime | None = None,
) -> str | None:
    """Calculate expiry timestamp for a given decay class.

    Args:
        decay_class: The decay tier classification
        base_time: Reference time (defaults to utcnow)

    Returns:
        ISO8601 timestamp string, or None for permanent notes.
    """
    ttl = DECAY_TTL.get(decay_class)
    if ttl is None:
        return None

    base = base_time or datetime.utcnow()
    expiry = base + timedelta(seconds=ttl)
    return expiry.isoformat()
