#!/bin/bash
#
# Claude Code SessionStart Hook
# 
# Loads project context and injects recent memories into the session.
# This hook runs when a new Claude Code session begins.

set -euo pipefail

# Configuration
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8000}"
PROJECT="${OBSIDIAN_MEMORY_PROJECT:-}"
SESSION_ID="${CLAUDE_SESSION_ID:-}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[obsidian-memory]${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[obsidian-memory]${NC} WARNING: $*" >&2
}

# Check if backend is available
if ! curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    warn "Backend not available at ${API_URL}, skipping context injection"
    exit 0
fi

log "SessionStart: Loading project context..."

# Create or get session
if [ -z "${SESSION_ID}" ]; then
    SESSION_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions" \
        -H "Content-Type: application/json" \
        -d "{\"project\": \"${PROJECT}\"}" 2>/dev/null || echo '{}')
    
    SESSION_ID=$(echo "${SESSION_RESPONSE}" | grep -o '"session_id":"[^"]*' | cut -d'"' -f4 || echo "")
    
    if [ -n "${SESSION_ID}" ]; then
        log "Session ID: ${SESSION_ID}"
        export OBSIDIAN_MEMORY_SESSION_ID="${SESSION_ID}"
    fi
else
    log "Using existing session: ${SESSION_ID}"
fi

# Get recent notes for context injection
if [ -n "${PROJECT}" ]; then
    log "Loading recent notes for project: ${PROJECT}"
    
    RECENT_NOTES=$(curl -s -X GET "${API_URL}/api/projects/${PROJECT}/notes?limit=5" 2>/dev/null || echo '{"notes":[]}')
    
    NOTE_COUNT=$(echo "${RECENT_NOTES}" | grep -o '"note_id"' | wc -l || echo "0")
    
    if [ "${NOTE_COUNT}" -gt 0 ]; then
        log "Found ${NOTE_COUNT} recent notes in project"
        # Notes are available via API, can be referenced in context
    fi
else
    # Get recent notes globally
    log "Loading recent notes..."
    RECENT_NOTES=$(curl -s -X POST "${API_URL}/api/notes/search" \
        -H "Content-Type: application/json" \
        -d '{"query":"*","limit":5,"sort":"updated_desc"}' 2>/dev/null || echo '{"notes":[]}')
fi

# Get project list if no project specified
if [ -z "${PROJECT}" ]; then
    PROJECTS=$(curl -s -X GET "${API_URL}/api/projects" 2>/dev/null || echo '{"projects":[]}')
    PROJECT_COUNT=$(echo "${PROJECTS}" | grep -o '"name"' | wc -l || echo "0")
    
    if [ "${PROJECT_COUNT}" -gt 0 ]; then
        log "Available projects: ${PROJECT_COUNT}"
    fi
fi

log "SessionStart complete"
