-- ============================================================================
-- Obsidian-Memory: Row Level Security Policies Migration
-- ============================================================================
-- This migration enables RLS on all tables and creates policies that ensure
-- users can only access their own data.
-- ============================================================================

-- ============================================================================
-- ENABLE ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- NOTES POLICIES
-- ============================================================================
-- Users can only access their own notes

-- SELECT: Users can view their own notes
CREATE POLICY "Users can view own notes"
    ON notes FOR SELECT
    USING (auth.uid() = user_id);

-- INSERT: Users can create notes for themselves
CREATE POLICY "Users can insert own notes"
    ON notes FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- UPDATE: Users can update their own notes
CREATE POLICY "Users can update own notes"
    ON notes FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- DELETE: Users can delete their own notes
CREATE POLICY "Users can delete own notes"
    ON notes FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================================
-- RELATIONS POLICIES
-- ============================================================================
-- Users can only access relations for their own notes

-- SELECT: Users can view relations from their notes
CREATE POLICY "Users can view own relations"
    ON relations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM notes
            WHERE notes.id = relations.source_id
            AND notes.user_id = auth.uid()
        )
    );

-- INSERT: Users can create relations for their notes
CREATE POLICY "Users can insert own relations"
    ON relations FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM notes
            WHERE notes.id = source_id
            AND notes.user_id = auth.uid()
        )
    );

-- UPDATE: Users can update relations for their notes
CREATE POLICY "Users can update own relations"
    ON relations FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM notes
            WHERE notes.id = relations.source_id
            AND notes.user_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM notes
            WHERE notes.id = source_id
            AND notes.user_id = auth.uid()
        )
    );

-- DELETE: Users can delete relations for their notes
CREATE POLICY "Users can delete own relations"
    ON relations FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM notes
            WHERE notes.id = relations.source_id
            AND notes.user_id = auth.uid()
        )
    );

-- ============================================================================
-- SESSIONS POLICIES
-- ============================================================================
-- Users can only access their own sessions

-- SELECT: Users can view their own sessions
CREATE POLICY "Users can view own sessions"
    ON sessions FOR SELECT
    USING (auth.uid() = user_id);

-- INSERT: Users can create sessions for themselves
CREATE POLICY "Users can insert own sessions"
    ON sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- UPDATE: Users can update their own sessions
CREATE POLICY "Users can update own sessions"
    ON sessions FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- DELETE: Users can delete their own sessions
CREATE POLICY "Users can delete own sessions"
    ON sessions FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================================
-- SERVICE ROLE BYPASS
-- ============================================================================
-- Note: The service_role key bypasses RLS by default in Supabase.
-- This allows backend services to access all data when needed.
-- For additional security, you can create specific policies for service roles.
