#!/bin/bash
#
# Claude Code PreCompact Hook
#
# Triggers AI summarization before context is lost.
# This hook runs before Claude Code compacts the context window.

set -euo pipefail

# Configuration
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8000}"
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"

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
    exit 0
fi

log "PreCompact: Triggering session summarization..."

# Trigger AI summarization
SUMMARY_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions/${SESSION_ID}/summary" 2>/dev/null || echo '{}')

# Check if summarization was successful
if echo "${SUMMARY_RESPONSE}" | grep -q "key_learnings"; then
    log "Session summarized successfully"
    
    # Extract key learnings count
    LEARNING_COUNT=$(echo "${SUMMARY_RESPONSE}" | grep -o '"key_learnings"' | wc -l || echo "0")
    if [ "${LEARNING_COUNT}" -gt 0 ]; then
        log "Captured ${LEARNING_COUNT} key learnings"
    fi
else
    warn "Summarization may have failed or AI is unavailable"
fi
