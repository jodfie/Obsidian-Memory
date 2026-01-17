#!/bin/bash
#
# Claude Code SessionEnd Hook
#
# Finalizes session, extracts patterns, and syncs.
# This hook runs when the Claude Code session ends.

set -euo pipefail

# Configuration
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8000}"
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
PROJECT="${OBSIDIAN_MEMORY_PROJECT:-}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[obsidian-memory]${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[obsidian-memory]${NC} WARNING: $*" >&2
}

# Skip if no session
if [ -z "${SESSION_ID}" ]; then
    exit 0
fi

# Check if backend is available
if ! curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    warn "Backend not available, skipping session finalization"
    exit 0
fi

log "SessionEnd: Finalizing session ${SESSION_ID}..."

# Generate final summary if not already done
log "Generating final session summary..."
SUMMARY_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions/${SESSION_ID}/summary" 2>/dev/null || echo '{}')

if echo "${SUMMARY_RESPONSE}" | grep -q "key_learnings"; then
    # Extract summary information
    KEY_LEARNINGS=$(echo "${SUMMARY_RESPONSE}" | grep -o '"key_learnings":\[[^]]*\]' | head -1 || echo "[]")
    DECISIONS=$(echo "${SUMMARY_RESPONSE}" | grep -o '"decisions":\[[^]]*\]' | head -1 || echo "[]")
    ERRORS=$(echo "${SUMMARY_RESPONSE}" | grep -o '"errors_encountered":\[[^]]*\]' | head -1 || echo "[]")
    
    log "Session summary generated:"
    log "  - Key learnings captured"
    log "  - Decisions recorded"
    log "  - Errors documented"
else
    warn "Could not generate session summary"
fi

# End the session
log "Ending session..."
END_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions/${SESSION_ID}/end" 2>/dev/null || echo '{}')

if echo "${END_RESPONSE}" | grep -q '"status":"completed"'; then
    log "Session finalized successfully"
else
    warn "Session end may have failed"
fi

# Extract patterns (future: use AI processor pattern detection)
# For now, just log that pattern extraction would happen here
log "Pattern extraction would be triggered here (future enhancement)"

log "SessionEnd complete"
