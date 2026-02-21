#!/usr/bin/env bash
# codex-om-notify.sh — Codex notify script for Obsidian-Memory integration
#
# Codex calls this script with a JSON argument on each agent-turn-complete event.
# It logs the turn as an observation to the OM API.
#
# Setup: Add to ~/.codex/config.toml:
#   notify = ["bash", "/path/to/codex-om-notify.sh"]
#
# Requires: curl, jq, OBSIDIAN_MEMORY_API_URL set in environment

set -euo pipefail

API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
SESSION_FILE="/tmp/obsidian-memory-codex-session.json"

# ── Parse Codex event JSON (passed as first argument) ──
EVENT="${1:-{}}"

EVENT_TYPE=$(echo "$EVENT" | jq -r '.type // empty' 2>/dev/null || echo "")
THREAD_ID=$(echo "$EVENT" | jq -r '.["thread-id"] // empty' 2>/dev/null || echo "")
TURN_ID=$(echo "$EVENT" | jq -r '.["turn-id"] // empty' 2>/dev/null || echo "")
CWD=$(echo "$EVENT" | jq -r '.cwd // empty' 2>/dev/null || echo "")
LAST_MSG=$(echo "$EVENT" | jq -r '.["last-assistant-message"] // empty' 2>/dev/null || echo "")
INPUT_MSGS=$(echo "$EVENT" | jq -c '.["input-messages"] // []' 2>/dev/null || echo "[]")

# Only handle agent-turn-complete (currently the only Codex event)
[ "$EVENT_TYPE" != "agent-turn-complete" ] && exit 0
[ -z "$THREAD_ID" ] && exit 0

# ── Session management ──
# Create or reuse an OM session keyed by Codex thread-id
SESSION_ID=""
if [ -f "$SESSION_FILE" ]; then
  SAVED_THREAD=$(jq -r '.thread_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
  if [ "$SAVED_THREAD" = "$THREAD_ID" ]; then
    SESSION_ID=$(jq -r '.session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
    API_URL=$(jq -r '.api_url // empty' "$SESSION_FILE" 2>/dev/null || echo "$API_URL")
  else
    rm -f "$SESSION_FILE"
  fi
fi

if [ -z "$SESSION_ID" ]; then
  # Create new OM session for this Codex thread
  PROJECT=$(basename "$CWD" 2>/dev/null || echo "")
  RESPONSE=$(curl -sf --connect-timeout 2 --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d "{\"session_id\": \"codex-${THREAD_ID}\", \"project\": \"${PROJECT}\"}" \
    "${API_URL}/api/sessions" 2>/dev/null || echo "")

  SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id // empty' 2>/dev/null || echo "")
  if [ -z "$SESSION_ID" ]; then
    echo "[om-codex] WARNING: Failed to create OM session" >&2
    exit 0
  fi

  jq -n \
    --arg sid "$SESSION_ID" \
    --arg tid "$THREAD_ID" \
    --arg url "$API_URL" \
    --arg proj "$PROJECT" \
    '{session_id: $sid, thread_id: $tid, api_url: $url, project: $proj}' \
    > "$SESSION_FILE"

  # Log session start
  curl -sf --connect-timeout 2 --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d "{\"session_id\": \"${SESSION_ID}\", \"event_type\": \"observation\", \"content\": \"Codex session started (thread: ${THREAD_ID}, project: ${PROJECT})\", \"metadata\": {\"source\": \"codex\", \"project\": \"${PROJECT}\"}}" \
    "${API_URL}/api/sessions/observe" >/dev/null 2>&1 || true
fi

# ── Log the turn as an observation ──
# Extract last user prompt from input-messages
USER_PROMPT=$(echo "$INPUT_MSGS" | jq -r 'map(select(.role == "user")) | last | .content // empty' 2>/dev/null || echo "")

# Truncate long messages to avoid bloating the observation
truncate() {
  local text="$1" max="${2:-500}"
  if [ ${#text} -gt "$max" ]; then
    echo "${text:0:$max}..."
  else
    echo "$text"
  fi
}

PROMPT_SHORT=$(truncate "$USER_PROMPT" 300)
RESPONSE_SHORT=$(truncate "$LAST_MSG" 500)

CONTENT="[Codex turn ${TURN_ID}] Prompt: ${PROMPT_SHORT}\nResponse: ${RESPONSE_SHORT}"
ESCAPED_CONTENT=$(echo "$CONTENT" | jq -Rs '.' 2>/dev/null || echo "\"$CONTENT\"")

curl -sf --connect-timeout 2 --max-time 5 \
  -X POST -H "Content-Type: application/json" \
  -d "{\"session_id\": \"${SESSION_ID}\", \"event_type\": \"codex_turn\", \"content\": ${ESCAPED_CONTENT}, \"metadata\": {\"source\": \"codex\", \"thread_id\": \"${THREAD_ID}\", \"turn_id\": \"${TURN_ID}\"}}" \
  "${API_URL}/api/sessions/observe" >/dev/null 2>&1 || true

exit 0
