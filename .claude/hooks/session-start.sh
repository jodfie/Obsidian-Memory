#!/usr/bin/env bash
# session-start.sh — SessionStart hook (sync, matcher: startup)
# Creates a new Obsidian-Memory session and persists env vars via CLAUDE_ENV_FILE.

source "$(dirname "$0")/_lib.sh"
read_input

# Extract fields from SessionStart input
CLAUDE_SESSION_ID=$(field "session_id")
SOURCE=$(field "source")
MODEL=$(field "model")
CWD=$(field "cwd")

# Derive project name from cwd (last directory component)
PROJECT=$(basename "$CWD" 2>/dev/null || echo "")

# Check if backend is available
if ! is_backend_up; then
  exit 0
fi

# Create session
RESPONSE=$(api_post "api/sessions" "{
  \"session_id\": \"${CLAUDE_SESSION_ID}\",
  \"project\": \"${PROJECT}\"
}")

# Extract session_id from response (backend may assign a different one)
BACKEND_SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id // empty' 2>/dev/null || echo "")
if [ -z "$BACKEND_SESSION_ID" ]; then
  BACKEND_SESSION_ID="$CLAUDE_SESSION_ID"
fi

# Persist env vars for all subsequent hooks and Bash commands
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export OBSIDIAN_MEMORY_SESSION_ID=\"${BACKEND_SESSION_ID}\"" >> "$CLAUDE_ENV_FILE"
  echo "export OBSIDIAN_MEMORY_API_URL=\"${API_URL}\"" >> "$CLAUDE_ENV_FILE"
  echo "export OBSIDIAN_MEMORY_PROJECT=\"${PROJECT}\"" >> "$CLAUDE_ENV_FILE"
fi

# Log the session start as first observation
SESSION_ID="$BACKEND_SESSION_ID"
observe_event "observation" "Session started: model=${MODEL}, source=${SOURCE}, project=${PROJECT}" \
  "{\"model\": \"${MODEL}\", \"source\": \"${SOURCE}\", \"project\": \"${PROJECT}\"}"

# Return context for Claude
jq -n --arg ctx "Obsidian-Memory session active: ${BACKEND_SESSION_ID} (project: ${PROJECT})" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'

exit 0
