#!/usr/bin/env bash
# session-start.sh — SessionStart hook (sync, matcher: startup|resume)
# Creates a new Obsidian-Memory session and persists state via session file + CLAUDE_ENV_FILE.

source "$(dirname "$0")/_lib.sh"
read_input

# ── Dedupe: if session file already exists for this Claude session, skip ──
CLAUDE_SESSION_ID=$(field "session_id")
if [ -f "$SESSION_FILE" ]; then
  EXISTING_ID=$(jq -r '.claude_session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
  if [ "$EXISTING_ID" = "$CLAUDE_SESSION_ID" ]; then
    # Already registered — return cached context
    BACKEND_SESSION_ID=$(jq -r '.session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
    PROJECT=$(jq -r '.project // empty' "$SESSION_FILE" 2>/dev/null || echo "")
    jq -n --arg ctx "Obsidian-Memory session active: ${BACKEND_SESSION_ID} (project: ${PROJECT})" '{
      hookSpecificOutput: {
        hookEventName: "SessionStart",
        additionalContext: $ctx
      }
    }'
    exit 0
  fi
fi

# ── Extract fields ──
SOURCE=$(field "source")
MODEL=$(field "model")
CWD=$(field "cwd")
PROJECT=$(basename "$CWD" 2>/dev/null || echo "")

# ── Check backend ──
if ! is_backend_up; then
  exit 0
fi

# ── Create session ──
RESPONSE=$(api_post "api/sessions" "{
  \"session_id\": \"${CLAUDE_SESSION_ID}\",
  \"project\": \"${PROJECT}\"
}")

BACKEND_SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id // empty' 2>/dev/null || echo "")
if [ -z "$BACKEND_SESSION_ID" ]; then
  BACKEND_SESSION_ID="$CLAUDE_SESSION_ID"
fi

# ── Write session file (shared state for all hooks) ──
jq -n \
  --arg sid "$BACKEND_SESSION_ID" \
  --arg csid "$CLAUDE_SESSION_ID" \
  --arg url "$API_URL" \
  --arg proj "$PROJECT" \
  '{session_id: $sid, claude_session_id: $csid, api_url: $url, project: $proj}' \
  > "$SESSION_FILE"

# ── Write CLAUDE_ENV_FILE (for Bash tool context) ──
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export OBSIDIAN_MEMORY_SESSION_ID=\"${BACKEND_SESSION_ID}\"" >> "$CLAUDE_ENV_FILE"
  echo "export OBSIDIAN_MEMORY_API_URL=\"${API_URL}\"" >> "$CLAUDE_ENV_FILE"
  echo "export OBSIDIAN_MEMORY_PROJECT=\"${PROJECT}\"" >> "$CLAUDE_ENV_FILE"
fi

# ── Log session start observation ──
SESSION_ID="$BACKEND_SESSION_ID"
observe_event "observation" "Session started: model=${MODEL}, source=${SOURCE}, project=${PROJECT}" \
  "{\"model\": \"${MODEL}\", \"source\": \"${SOURCE}\", \"project\": \"${PROJECT}\"}"

# ── Return context for Claude ──
jq -n --arg ctx "Obsidian-Memory session active: ${BACKEND_SESSION_ID} (project: ${PROJECT})" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'

exit 0
