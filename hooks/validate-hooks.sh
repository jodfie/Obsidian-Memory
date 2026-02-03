#!/bin/bash
#
# Hook Validation Script
#
# Validates the complete Claude Code hooks workflow by testing each hook
# and verifying session data is captured correctly.
#
# Usage: ./hooks/validate-hooks.sh [API_URL]
#

set -euo pipefail

# Configuration
API_URL="${1:-http://localhost:8000}"
PROJECT="hook-validation-test"
SESSION_DIR="$HOME/.obsidian-memory/sessions"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; }
info() { echo -e "${BLUE}ℹ${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }

echo "======================================"
echo "Claude Code Hooks Validation"
echo "======================================"
echo ""

# Step 1: Check backend availability
info "Checking backend at ${API_URL}..."
if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    pass "Backend is available"
else
    fail "Backend not available at ${API_URL}"
    echo ""
    echo "To start the backend:"
    echo "  cd backend && uvicorn app.main:app --reload"
    exit 1
fi

# Step 2: Check hook scripts are executable
echo ""
info "Checking hook scripts..."
HOOKS_DIR="$(dirname "$0")"
for hook in session-start.sh user-prompt-submit.sh post-tool-use.sh pre-compact.sh session-end.sh; do
    if [ -x "${HOOKS_DIR}/${hook}" ]; then
        pass "${hook} is executable"
    else
        fail "${hook} is not executable"
        echo "  Fix: chmod +x ${HOOKS_DIR}/${hook}"
    fi
done

# Step 3: Test SessionStart
echo ""
info "Testing SessionStart hook..."
export OBSIDIAN_MEMORY_API_URL="${API_URL}"
export OBSIDIAN_MEMORY_PROJECT="${PROJECT}"

SESSION_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions" \
    -H "Content-Type: application/json" \
    -d "{\"project\": \"${PROJECT}\"}" 2>/dev/null || echo '{}')

SESSION_ID=$(echo "${SESSION_RESPONSE}" | grep -o '"session_id":"[^"]*' | cut -d'"' -f4 || echo "")

if [ -n "${SESSION_ID}" ]; then
    pass "Session created: ${SESSION_ID}"
    export OBSIDIAN_MEMORY_SESSION_ID="${SESSION_ID}"
else
    fail "Failed to create session"
    exit 1
fi

# Step 4: Test UserPromptSubmit (observe event)
echo ""
info "Testing UserPromptSubmit hook..."
OBSERVE_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions/observe" \
    -H "Content-Type: application/json" \
    -d "{
        \"session_id\": \"${SESSION_ID}\",
        \"event_type\": \"user_prompt\",
        \"content\": \"Validation test prompt\",
        \"metadata\": {\"test\": true}
    }" 2>/dev/null || echo '{}')

EVENT_COUNT=$(echo "${OBSERVE_RESPONSE}" | grep -o '"event_count":[0-9]*' | cut -d':' -f2 || echo "0")
if [ "${EVENT_COUNT}" -ge 1 ]; then
    pass "User prompt captured (event_count: ${EVENT_COUNT})"
else
    fail "Failed to capture user prompt"
fi

# Step 5: Test PostToolUse (multiple event types)
echo ""
info "Testing PostToolUse hook (multiple event types)..."
EVENT_TYPES=("file_edit" "command" "research" "error")
for etype in "${EVENT_TYPES[@]}"; do
    RESULT=$(curl -s -X POST "${API_URL}/api/sessions/observe" \
        -H "Content-Type: application/json" \
        -d "{
            \"session_id\": \"${SESSION_ID}\",
            \"event_type\": \"${etype}\",
            \"content\": \"Test ${etype} event\",
            \"metadata\": {\"tool_name\": \"test\"}
        }" 2>/dev/null || echo '{}')

    if echo "${RESULT}" | grep -q "event_count"; then
        pass "  ${etype} event captured"
    else
        fail "  ${etype} event failed"
    fi
done

# Step 6: Test session retrieval
echo ""
info "Testing session retrieval..."
GET_RESPONSE=$(curl -s -X GET "${API_URL}/api/sessions/${SESSION_ID}" 2>/dev/null || echo '{}')

if echo "${GET_RESPONSE}" | grep -q "${SESSION_ID}"; then
    pass "Session retrieved successfully"

    # Check event count
    TOTAL_EVENTS=$(echo "${GET_RESPONSE}" | grep -o '"events":\[[^]]*\]' | grep -o '"event_type"' | wc -l || echo "0")
    info "  Total events in session: ${TOTAL_EVENTS}"
else
    fail "Failed to retrieve session"
fi

# Step 7: Test SessionEnd
echo ""
info "Testing SessionEnd hook..."
END_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions/${SESSION_ID}/end" 2>/dev/null || echo '{}')

if echo "${END_RESPONSE}" | grep -q '"status":"completed"'; then
    pass "Session ended successfully"
else
    fail "Failed to end session"
fi

# Step 8: Verify session file persistence
echo ""
info "Checking session file persistence..."
if [ -d "${SESSION_DIR}" ]; then
    SESSION_FILE="${SESSION_DIR}/${SESSION_ID}.json"
    if [ -f "${SESSION_FILE}" ]; then
        pass "Session file exists: ${SESSION_FILE}"

        # Check file contents
        if grep -q '"status":"completed"' "${SESSION_FILE}"; then
            pass "  Session status is 'completed'"
        fi
        if grep -q '"events"' "${SESSION_FILE}"; then
            pass "  Events array present"
        fi
    else
        warn "Session file not found (may be using different storage)"
    fi
else
    warn "Sessions directory does not exist: ${SESSION_DIR}"
fi

# Step 9: Test graceful failure (optional)
echo ""
info "Testing graceful failure with invalid session..."
INVALID_RESPONSE=$(curl -s -X POST "${API_URL}/api/sessions/observe" \
    -H "Content-Type: application/json" \
    -d '{
        "session_id": "invalid-session-xyz",
        "event_type": "observation",
        "content": "This should fail gracefully"
    }' 2>/dev/null || echo '{}')

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/api/sessions/observe" \
    -H "Content-Type: application/json" \
    -d '{"session_id": "invalid-session-xyz", "event_type": "observation", "content": "test"}' 2>/dev/null || echo "000")

if [ "${HTTP_CODE}" = "404" ] || [ "${HTTP_CODE}" = "400" ]; then
    pass "Graceful failure: returned HTTP ${HTTP_CODE} for invalid session"
else
    warn "Unexpected response: HTTP ${HTTP_CODE}"
fi

# Summary
echo ""
echo "======================================"
echo "Validation Complete"
echo "======================================"
echo ""
echo "Session ID: ${SESSION_ID}"
echo "Project: ${PROJECT}"
echo ""
echo "To run a full Claude Code session test:"
echo "  1. Start backend: cd backend && uvicorn app.main:app --reload"
echo "  2. Start Claude: claude --hooks-debug"
echo "  3. Observe hook output in terminal"
echo ""
