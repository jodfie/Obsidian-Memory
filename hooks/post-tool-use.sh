#!/bin/bash
#
# Claude Code PostToolUse Hook
#
# Captures file edits, commands, errors, and web research after tool usage.
# This hook runs after a tool is executed.

set -euo pipefail

# Configuration
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8000}"
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
PROJECT="${OBSIDIAN_MEMORY_PROJECT:-}"

# Tool information (passed as arguments or environment)
TOOL_NAME="${1:-}"
TOOL_RESULT="${2:-}"
TOOL_ERROR="${3:-}"

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

# Determine event type based on tool name
EVENT_TYPE="tool_use"
if [[ "${TOOL_NAME}" == *"file"* ]] || [[ "${TOOL_NAME}" == *"write"* ]] || [[ "${TOOL_NAME}" == *"edit"* ]]; then
    EVENT_TYPE="file_edit"
elif [[ "${TOOL_NAME}" == *"command"* ]] || [[ "${TOOL_NAME}" == *"bash"* ]] || [[ "${TOOL_NAME}" == *"run"* ]]; then
    EVENT_TYPE="command"
elif [[ "${TOOL_NAME}" == *"search"* ]] || [[ "${TOOL_NAME}" == *"web"* ]] || [[ "${TOOL_NAME}" == *"research"* ]]; then
    EVENT_TYPE="research"
fi

# Capture tool usage
CONTENT="Tool: ${TOOL_NAME}"
if [ -n "${TOOL_ERROR}" ]; then
    EVENT_TYPE="error"
    CONTENT="Error in ${TOOL_NAME}: ${TOOL_ERROR}"
elif [ -n "${TOOL_RESULT}" ]; then
    RESULT_PREVIEW=$(echo "${TOOL_RESULT}" | head -c 200)
    CONTENT="Tool: ${TOOL_NAME} - Result: ${RESULT_PREVIEW}"
fi

# Escape JSON special characters in content
ESCAPED_CONTENT=$(echo "${CONTENT}" | sed 's/"/\\"/g' | sed 's/\\/\\\\/g')

# Log observation
curl -s -X POST "${API_URL}/api/sessions/observe" \
    -H "Content-Type: application/json" \
    -d "{
        \"session_id\": \"${SESSION_ID}\",
        \"event_type\": \"${EVENT_TYPE}\",
        \"content\": \"${ESCAPED_CONTENT}\",
        \"metadata\": {
            \"tool_name\": \"${TOOL_NAME}\",
            \"project\": \"${PROJECT}\",
            \"has_error\": $([ -n "${TOOL_ERROR}" ] && echo "true" || echo "false")
        }
    }" > /dev/null 2>&1 || true

# If it's a file edit, try to capture the file content
if [ "${EVENT_TYPE}" = "file_edit" ] && [ -n "${TOOL_RESULT}" ]; then
    # Extract file path from result if possible
    FILE_PATH=$(echo "${TOOL_RESULT}" | grep -oE '\/[^\s]+\.(py|ts|tsx|js|jsx|md|json|yaml|yml)' | head -1 || echo "")
    
    if [ -n "${FILE_PATH}" ] && [ -f "${FILE_PATH}" ]; then
        log "Captured file edit: ${FILE_PATH}"
        # Could create a note about this file edit here
    fi
fi
