-- ============================================================================
-- Obsidian-Memory: Performance Indexes Migration
-- ============================================================================
-- This migration creates indexes for optimal query performance.
-- Includes full-text search, foreign key indexes, and common query patterns.
-- ============================================================================

-- ============================================================================
-- FULL-TEXT SEARCH INDEX
-- ============================================================================
-- GIN index for full-text search on notes (title + content)
-- Uses English text search configuration

CREATE INDEX notes_fts_idx ON notes
    USING gin(to_tsvector('english', title || ' ' || content));

-- Add index comment
COMMENT ON INDEX notes_fts_idx IS 'Full-text search index on title and content';

-- ============================================================================
-- NOTES TABLE INDEXES
-- ============================================================================

-- Index on user_id for filtering notes by user (RLS queries)
CREATE INDEX notes_user_id_idx ON notes(user_id);

-- Index on path for lookups by file path (unique constraint already creates one, but explicit is clearer)
CREATE INDEX notes_path_idx ON notes(path);

-- Index on updated_at for sorting by recency (most recent first)
CREATE INDEX notes_updated_at_idx ON notes(updated_at DESC);

-- Composite index for common query pattern: user's notes sorted by update time
CREATE INDEX notes_user_updated_idx ON notes(user_id, updated_at DESC);

-- Index on frontmatter for JSONB queries (e.g., filtering by tags in frontmatter)
CREATE INDEX notes_frontmatter_idx ON notes USING gin(frontmatter);

-- Add index comments
COMMENT ON INDEX notes_user_id_idx IS 'Filter notes by user for RLS policies';
COMMENT ON INDEX notes_path_idx IS 'Fast lookups by file path';
COMMENT ON INDEX notes_updated_at_idx IS 'Sort notes by recency';
COMMENT ON INDEX notes_user_updated_idx IS 'Common query: user notes sorted by update time';
COMMENT ON INDEX notes_frontmatter_idx IS 'JSONB queries on frontmatter metadata';

-- ============================================================================
-- RELATIONS TABLE INDEXES
-- ============================================================================

-- Index on source_id for finding outgoing links from a note
CREATE INDEX relations_source_id_idx ON relations(source_id);

-- Index on target_path for finding backlinks to a note
CREATE INDEX relations_target_path_idx ON relations(target_path);

-- Index on relation_type for filtering by link type
CREATE INDEX relations_type_idx ON relations(relation_type);

-- Composite index for common query: all relations from a source note
CREATE INDEX relations_source_type_idx ON relations(source_id, relation_type);

-- Add index comments
COMMENT ON INDEX relations_source_id_idx IS 'Find outgoing links from a note';
COMMENT ON INDEX relations_target_path_idx IS 'Find backlinks to a note';
COMMENT ON INDEX relations_type_idx IS 'Filter relations by type';
COMMENT ON INDEX relations_source_type_idx IS 'Find relations from a note by type';

-- ============================================================================
-- SESSIONS TABLE INDEXES
-- ============================================================================

-- Index on user_id for filtering sessions by user
CREATE INDEX sessions_user_id_idx ON sessions(user_id);

-- Index on started_at for sorting and date range queries
CREATE INDEX sessions_started_at_idx ON sessions(started_at DESC);

-- Index on project for filtering sessions by project
CREATE INDEX sessions_project_idx ON sessions(project);

-- Composite index for common query: user's recent sessions
CREATE INDEX sessions_user_started_idx ON sessions(user_id, started_at DESC);

-- Add index comments
COMMENT ON INDEX sessions_user_id_idx IS 'Filter sessions by user';
COMMENT ON INDEX sessions_started_at_idx IS 'Sort sessions by start time';
COMMENT ON INDEX sessions_project_idx IS 'Filter sessions by project';
COMMENT ON INDEX sessions_user_started_idx IS 'User sessions sorted by recency';
