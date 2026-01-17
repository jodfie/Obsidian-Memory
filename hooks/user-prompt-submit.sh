#!/bin/bash
#
# Claude Code UserPromptSubmit Hook
#
# Logs user intent for session tracking.
# This hook runs when the user submits a prompt.

set -euo pipefail

# Configuration
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8000}"
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
PROJECT="${OBSIDIAN_MEMORY_PROJECT:-}"

# Get user prompt from stdin or environment
USER_PROMPT="${1:-}"
if [ -z "${USER_PROMPT}" ] && [ ! -t 0 ]; then
    USER_PROMPT=$(cat)
fi

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

# Log user prompt as observation
if [ -n "${USER_PROMPT}" ]; then
    # Truncate prompt if too long
    PROMPT_PREVIEW=$(echo "${USER_PROMPT}" | head -c 500)
    # Escape JSON special characters
    ESCAPED_PROMPT=$(echo "User prompt: ${PROMPT_PREVIEW}" | sed 's/"/\\"/g' | sed 's/\\/\\\\/g')
    PROMPT_LENGTH=$(echo -n "${USER_PROMPT}" | wc -c)
    
    curl -s -X POST "${API_URL}/api/sessions/observe" \
        -H "Content-Type: application/json" \
        -d "{
            \"session_id\": \"${SESSION_ID}\",
            \"event_type\": \"user_prompt\",
            \"content\": \"${ESCAPED_PROMPT}\",
            \"metadata\": {
                \"project\": \"${PROJECT}\",
                \"prompt_length\": ${PROMPT_LENGTH}
            }
        }" > /dev/null 2>&1 || true
    
    log "Logged user prompt to session"
fi
