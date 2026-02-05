-- ============================================================================
-- Obsidian-Memory: Initial Schema Migration
-- ============================================================================
-- This migration creates the core tables for the Obsidian-Memory system.
-- Tables: notes, relations, sessions
-- ============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- NOTES TABLE
-- ============================================================================
-- Core notes table (replaces .md files on disk)
-- Each note represents a markdown document with metadata stored as JSONB

CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path TEXT NOT NULL UNIQUE,           -- e.g., "projects/obsidian-memory/design.md"
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',    -- markdown body
    frontmatter JSONB DEFAULT '{}',      -- YAML metadata as JSON
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE
);

-- Add table comment
COMMENT ON TABLE notes IS 'Core notes storage - replaces markdown files on disk';
COMMENT ON COLUMN notes.path IS 'Virtual file path, e.g., "projects/obsidian-memory/design.md"';
COMMENT ON COLUMN notes.frontmatter IS 'YAML frontmatter stored as JSON object';

-- ============================================================================
-- RELATIONS TABLE
-- ============================================================================
-- Extracted relations between notes (wikilinks, tags, observations)
-- Enables graph queries and backlink functionality

CREATE TABLE relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    target_path TEXT NOT NULL,           -- path of linked note (may not exist yet)
    relation_type TEXT NOT NULL,         -- 'wikilink', 'tag', 'observation', 'embed'
    context TEXT,                        -- surrounding text for context
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add table comment
COMMENT ON TABLE relations IS 'Extracted relations between notes (links, tags, etc.)';
COMMENT ON COLUMN relations.target_path IS 'Path of linked note - may reference notes that do not exist yet';
COMMENT ON COLUMN relations.relation_type IS 'Type of relation: wikilink, tag, observation, embed';
COMMENT ON COLUMN relations.context IS 'Surrounding text providing context for the relation';

-- Add constraint for valid relation types
ALTER TABLE relations ADD CONSTRAINT valid_relation_type
    CHECK (relation_type IN ('wikilink', 'tag', 'observation', 'embed', 'reference'));

-- ============================================================================
-- SESSIONS TABLE
-- ============================================================================
-- Claude Code interaction sessions for tracking AI conversations and changes

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project TEXT,                        -- project/context identifier
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    summary TEXT,                        -- AI-generated summary of session
    events JSONB DEFAULT '[]'::jsonb,    -- array of session events
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE
);

-- Add table comment
COMMENT ON TABLE sessions IS 'Claude Code interaction sessions for tracking AI conversations';
COMMENT ON COLUMN sessions.events IS 'JSON array of session events with timestamps and details';
COMMENT ON COLUMN sessions.summary IS 'AI-generated summary of the session activities';

-- ============================================================================
-- UPDATED_AT TRIGGER
-- ============================================================================
-- Automatically update the updated_at timestamp when a row is modified

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to notes table
CREATE TRIGGER notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
