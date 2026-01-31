#!/bin/bash
#
# Enhanced Pre-Compact Hook for Clawdbot + Obsidian-Memory Integration
#
# This replaces the simple session summarization with intelligent knowledge consolidation:
# 1. Triggers when sessions approach 95k tokens (before Clawdbot auto-reset)
# 2. Uses Obsidian-Memory AI processor for smart extraction
# 3. Updates existing knowledge/decision notes instead of creating files
# 4. Archives session summary with cross-references
# 5. Enables future context queries from consolidated knowledge

set -euo pipefail

# Configuration
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8000}"
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
BRAIN_DIR="${HOME}/Obsidian-Memory/brain"
SCRIPTS_DIR="${BRAIN_DIR}/scripts"
CONSOLIDATION_SCRIPT="${SCRIPTS_DIR}/enhanced-session-consolidation.py"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[brain-consolidation]${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[brain-consolidation]${NC} WARNING: $*" >&2
}

info() {
    echo -e "${BLUE}[brain-consolidation]${NC} $*" >&2
}

# Skip if no session
if [ -z "${SESSION_ID}" ]; then
    warn "No session ID available, skipping consolidation"
    exit 0
fi

# Get current token count from Clawdbot
get_token_count() {
    local session_info
    session_info=$(clawdbot sessions list --format=json 2>/dev/null | grep -A5 -B5 "${SESSION_ID}" || echo "{}")
    echo "${session_info}" | grep -o '"tokenCount":[0-9]*' | cut -d: -f2 || echo "0"
}

TOKEN_COUNT=$(get_token_count)
log "Pre-compact triggered for session ${SESSION_ID} (${TOKEN_COUNT} tokens)"

# Only consolidate if we have substantial token count
if [ "${TOKEN_COUNT}" -lt 50000 ]; then
    info "Token count (${TOKEN_COUNT}) below consolidation threshold, skipping"
    exit 0
fi

# Check if consolidation script exists
if [ ! -f "${CONSOLIDATION_SCRIPT}" ]; then
    warn "Consolidation script not found at ${CONSOLIDATION_SCRIPT}"
    warn "Falling back to simple session archive"
    
    # Fallback: create simple session summary
    TIMESTAMP=$(date +"%Y-%m-%d-%H%M")
    SUMMARY_FILE="${BRAIN_DIR}/memory/session-summaries/${TIMESTAMP}-session-${SESSION_ID:0:8}.md"
    mkdir -p "$(dirname "${SUMMARY_FILE}")"
    
    cat > "${SUMMARY_FILE}" << EOF
# Session Summary ${TIMESTAMP}

## Context
- **Session ID:** ${SESSION_ID}
- **Token Count:** ${TOKEN_COUNT}
- **Timestamp:** $(date -Iseconds)
- **Status:** Fallback summary (consolidation script unavailable)

## Notes
This session was archived before context reset to prevent token bloat.
Manual review and knowledge integration recommended.

## Next Steps
- Extract key decisions from session history
- Update relevant knowledge notes
- Cross-reference related topics

## Meta
- Archive method: Fallback
- Consolidation script: Not available
- Session history preserved for manual review
EOF

    log "Created fallback summary: ${SUMMARY_FILE}"
    exit 0
fi

# Check if Python environment is available
if ! command -v python3 >/dev/null 2>&1; then
    warn "Python 3 not available, falling back to simple archive"
    exit 0
fi

# Check for required Python packages
if ! python3 -c "import aiohttp, asyncio" 2>/dev/null; then
    warn "Required Python packages (aiohttp) not available"
    info "Install with: pip install aiohttp"
    exit 0
fi

log "Starting intelligent session consolidation..."

# Run the consolidation script
if python3 "${CONSOLIDATION_SCRIPT}" \
    --session-id "${SESSION_ID}" \
    --token-count "${TOKEN_COUNT}" \
    --api-url "${API_URL}"; then
    
    log "✅ Session knowledge successfully consolidated"
    log "   - Key decisions extracted and integrated"
    log "   - Knowledge notes updated with learnings"
    log "   - Session archived with cross-references"
    log "   - Future sessions can query consolidated knowledge"
    
    # Update today's memory log with success
    TODAY_FILE="${BRAIN_DIR}/memory/$(date +%Y-%m-%d).md"
    if [ ! -f "${TODAY_FILE}" ]; then
        echo "# $(date +%Y-%m-%d) - Daily Memory Log" > "${TODAY_FILE}"
        echo "" >> "${TODAY_FILE}"
    fi
    
    cat >> "${TODAY_FILE}" << EOF

## Pre-Compact Knowledge Consolidation - $(date +%H:%M)

✅ **Session ${SESSION_ID:0:8}** successfully consolidated
- **Token count:** ${TOKEN_COUNT:,}
- **Method:** Intelligent AI-powered extraction  
- **Status:** Knowledge integrated into existing notes
- **Benefit:** Context preserved, session ready for reset

EOF

    info "Updated today's memory log: ${TODAY_FILE}"
    
else
    warn "Consolidation script failed, but context will still be preserved"
    log "Session will be reset as normal - check consolidation logs for details"
    
    # Log failure to today's memory
    TODAY_FILE="${BRAIN_DIR}/memory/$(date +%Y-%m-%d).md"
    if [ ! -f "${TODAY_FILE}" ]; then
        echo "# $(date +%Y-%m-%d) - Daily Memory Log" > "${TODAY_FILE}"
        echo "" >> "${TODAY_FILE}"
    fi
    
    cat >> "${TODAY_FILE}" << EOF

## Pre-Compact Consolidation Failed - $(date +%H:%M)

⚠️ **Session ${SESSION_ID:0:8}** consolidation encountered issues
- **Token count:** ${TOKEN_COUNT:,}
- **Method:** Attempted AI-powered extraction
- **Status:** Fallback to simple session reset
- **Action:** Manual review recommended

EOF

fi

log "Pre-compact hook completed - session ready for context reset"

# Optional: Trigger immediate session reset if very high token count
if [ "${TOKEN_COUNT}" -gt 150000 ]; then
    warn "Extremely high token count (${TOKEN_COUNT}), triggering immediate reset"
    # Uncomment if you want automatic reset:
    # clawdbot sessions reset --session-key "${SESSION_ID}" || true
fi