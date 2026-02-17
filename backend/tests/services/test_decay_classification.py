"""Tests for decay auto-classification logic."""

from datetime import datetime, timedelta

import pytest

from app.services.decay_classifier import (
    DECAY_TTL,
    VALID_DECAY_CLASSES,
    calculate_expiry,
    classify_decay,
)


class TestDecayConstants:
    """Test decay constants and configuration."""

    def test_all_five_decay_classes_defined(self):
        assert VALID_DECAY_CLASSES == {'permanent', 'stable', 'active', 'session', 'checkpoint'}

    def test_ttl_values(self):
        assert DECAY_TTL['permanent'] is None
        assert DECAY_TTL['stable'] == 90 * 24 * 3600
        assert DECAY_TTL['active'] == 14 * 24 * 3600
        assert DECAY_TTL['session'] == 24 * 3600
        assert DECAY_TTL['checkpoint'] == 4 * 3600


class TestClassifyDecayFrontmatter:
    """Test priority 1: explicit frontmatter override."""

    def test_frontmatter_permanent(self):
        assert classify_decay('note', [], {'decay_class': 'permanent'}, '') == 'permanent'

    def test_frontmatter_checkpoint(self):
        assert classify_decay('note', [], {'decay_class': 'checkpoint'}, '') == 'checkpoint'

    def test_frontmatter_overrides_note_type(self):
        # decision -> permanent normally, but frontmatter says checkpoint
        assert classify_decay('decision', [], {'decay_class': 'checkpoint'}, '') == 'checkpoint'

    def test_frontmatter_overrides_tags(self):
        assert classify_decay('note', ['#wip'], {'decay_class': 'permanent'}, '') == 'permanent'

    def test_invalid_frontmatter_falls_through(self):
        # Invalid value should fall through to next priority
        assert classify_decay('decision', [], {'decay_class': 'invalid'}, '') == 'permanent'

    def test_frontmatter_all_valid_classes(self):
        for cls in VALID_DECAY_CLASSES:
            assert classify_decay('note', [], {'decay_class': cls}, '') == cls

    def test_frontmatter_key_absent(self):
        # No decay_class key in frontmatter -> fall through
        assert classify_decay('note', [], {}, '') == 'stable'


class TestClassifyDecayNoteType:
    """Test priority 2: note type mapping."""

    def test_decision_is_permanent(self):
        assert classify_decay('decision', [], {}, '') == 'permanent'

    def test_session_is_session(self):
        assert classify_decay('session', [], {}, '') == 'session'

    def test_error_is_active(self):
        assert classify_decay('error', [], {}, '') == 'active'

    def test_note_type_falls_through(self):
        assert classify_decay('note', [], {}, '') == 'stable'

    def test_knowledge_type_falls_through(self):
        assert classify_decay('knowledge', [], {}, '') == 'stable'

    def test_research_type_falls_through(self):
        assert classify_decay('research', [], {}, '') == 'stable'


class TestClassifyDecayTags:
    """Test priority 3: tag-based rules."""

    def test_permanent_tag(self):
        assert classify_decay('note', ['permanent'], {}, '') == 'permanent'

    def test_architecture_tag(self):
        assert classify_decay('note', ['architecture'], {}, '') == 'permanent'

    def test_convention_tag(self):
        assert classify_decay('note', ['convention'], {}, '') == 'permanent'

    def test_checkpoint_tag(self):
        assert classify_decay('note', ['checkpoint'], {}, '') == 'checkpoint'

    def test_preflight_tag(self):
        assert classify_decay('note', ['preflight'], {}, '') == 'checkpoint'

    def test_debug_tag(self):
        assert classify_decay('note', ['debug'], {}, '') == 'session'

    def test_temp_tag(self):
        assert classify_decay('note', ['temp'], {}, '') == 'session'

    def test_temporary_tag(self):
        assert classify_decay('note', ['temporary'], {}, '') == 'session'

    def test_wip_tag(self):
        assert classify_decay('note', ['wip'], {}, '') == 'active'

    def test_sprint_tag(self):
        assert classify_decay('note', ['sprint'], {}, '') == 'active'

    def test_task_tag(self):
        assert classify_decay('note', ['task'], {}, '') == 'active'

    def test_todo_tag(self):
        assert classify_decay('note', ['todo'], {}, '') == 'active'

    def test_tag_with_hash_prefix(self):
        assert classify_decay('note', ['#permanent'], {}, '') == 'permanent'
        assert classify_decay('note', ['#debug'], {}, '') == 'session'

    def test_tag_case_insensitive(self):
        assert classify_decay('note', ['PERMANENT'], {}, '') == 'permanent'
        assert classify_decay('note', ['WIP'], {}, '') == 'active'
        assert classify_decay('note', ['Debug'], {}, '') == 'session'

    def test_tag_priority_permanent_over_active(self):
        # If both present, permanent wins (checked first)
        assert classify_decay('note', ['permanent', 'wip'], {}, '') == 'permanent'

    def test_tag_priority_checkpoint_over_session(self):
        assert classify_decay('note', ['checkpoint', 'debug'], {}, '') == 'checkpoint'

    def test_unrecognized_tag_falls_through(self):
        assert classify_decay('note', ['python', 'fastapi'], {}, '') == 'stable'


class TestClassifyDecayContent:
    """Test priority 4: content pattern matching."""

    def test_decided_to_use(self):
        assert classify_decay('note', [], {}, 'We decided to use FastAPI') == 'permanent'

    def test_chose_x(self):
        assert classify_decay('note', [], {}, 'Chose SQLite over Postgres') == 'permanent'

    def test_always_x(self):
        assert classify_decay('note', [], {}, 'Always run tests before deploy') == 'permanent'

    def test_never_x(self):
        assert classify_decay('note', [], {}, 'Never store passwords in plaintext') == 'permanent'

    def test_went_with(self):
        assert classify_decay('note', [], {}, 'Went with Docker for deployment') == 'permanent'

    def test_convention_word(self):
        assert classify_decay('note', [], {}, 'This is the convention for naming') == 'permanent'

    def test_architecture_word(self):
        assert classify_decay('note', [], {}, 'The architecture uses microservices') == 'permanent'

    def test_currently_debugging(self):
        assert classify_decay('note', [], {}, 'Currently debugging the auth flow') == 'session'

    def test_right_now(self):
        assert classify_decay('note', [], {}, 'Working on this right now') == 'session'

    def test_this_session(self):
        assert classify_decay('note', [], {}, 'Findings from this session') == 'session'

    def test_temporary_fix(self):
        assert classify_decay('note', [], {}, 'Applied a temporary fix') == 'session'

    def test_working_on(self):
        assert classify_decay('note', [], {}, 'Working on the API refactor') == 'active'

    def test_todo_in_content(self):
        assert classify_decay('note', [], {}, 'TODO: fix the login bug') == 'active'

    def test_blocker(self):
        assert classify_decay('note', [], {}, 'This is a blocker for release') == 'active'

    def test_content_case_insensitive(self):
        assert classify_decay('note', [], {}, 'DECIDED to use X') == 'permanent'
        assert classify_decay('note', [], {}, 'CURRENTLY DEBUGGING') == 'session'

    def test_content_priority_permanent_over_session(self):
        # Text with both decision and session language - permanent checked first
        text = 'We decided to use a temporary fix for this session'
        assert classify_decay('note', [], {}, text) == 'permanent'

    def test_no_matching_content(self):
        assert classify_decay('note', [], {}, 'Just a regular note about nothing special') == 'stable'


class TestClassifyDecayDefault:
    """Test priority 5: default fallback."""

    def test_empty_note(self):
        assert classify_decay('note', [], {}, '') == 'stable'

    def test_empty_everything(self):
        assert classify_decay('', [], {}, '') == 'stable'


class TestCalculateExpiry:
    """Test expiry timestamp calculation."""

    def test_permanent_returns_none(self):
        assert calculate_expiry('permanent') is None

    def test_stable_90_days(self):
        base = datetime(2026, 1, 1, 0, 0, 0)
        result = calculate_expiry('stable', base)
        expected = (base + timedelta(days=90)).isoformat()
        assert result == expected

    def test_active_14_days(self):
        base = datetime(2026, 1, 1, 0, 0, 0)
        result = calculate_expiry('active', base)
        expected = (base + timedelta(days=14)).isoformat()
        assert result == expected

    def test_session_24_hours(self):
        base = datetime(2026, 1, 1, 0, 0, 0)
        result = calculate_expiry('session', base)
        expected = (base + timedelta(hours=24)).isoformat()
        assert result == expected

    def test_checkpoint_4_hours(self):
        base = datetime(2026, 1, 1, 0, 0, 0)
        result = calculate_expiry('checkpoint', base)
        expected = (base + timedelta(hours=4)).isoformat()
        assert result == expected

    def test_no_base_time_uses_utcnow(self):
        result = calculate_expiry('session')
        assert result is not None
        # Should be roughly 24h from now
        expiry = datetime.fromisoformat(result)
        diff = expiry - datetime.utcnow()
        assert timedelta(hours=23) < diff < timedelta(hours=25)

    def test_returns_iso_format(self):
        base = datetime(2026, 6, 15, 14, 30, 0)
        result = calculate_expiry('checkpoint', base)
        assert result == '2026-06-15T18:30:00'
