#!/usr/bin/env bash
# copilot-om-hook.sh — GitHub Copilot CLI hook handler for Obsidian-Memory
#
# Copilot CLI passes JSON via stdin for all hook events.
# This single script handles all events by reading the event type from the JSON.
#
# Setup: Add hooks.json to your project or globally:
#   .github/hooks/hooks.json (project) or ~/.config/github-copilot/hooks.json (global)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/om-hook-common.sh"

_OM_SOURCE="copilot"
_OM_SESSION_FILE="/tmp/obsidian-memory-copilot-session.json"

# Read event JSON from stdin
INPUT=$(cat 2>/dev/null || echo '{}')
EVENT_TYPE="${1:-}"  # Copilot passes event name as argument
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || echo "")
PROJECT=$(basename "$CWD" 2>/dev/null || echo "")

case "$EVENT_TYPE" in
  sessionStart)
    SOURCE=$(echo "$INPUT" | jq -r '.source // empty' 2>/dev/null || echo "")
    PROMPT=$(echo "$INPUT" | jq -r '.initialPrompt // empty' 2>/dev/null || echo "")
    # Use timestamp as session ID since Copilot doesn't provide one
    COPILOT_SID="$(date +%s)-$$"
    om_session_ensure "$COPILOT_SID" "$PROJECT"
    om_observe "observation" "Copilot session started (source=${SOURCE}): ${PROMPT:0:200}" \
      "{\"source\": \"copilot\", \"project\": \"${PROJECT}\"}"
    ;;

  sessionEnd)
    REASON=$(echo "$INPUT" | jq -r '.reason // empty' 2>/dev/null || echo "")
    _om_load_session
    om_observe "observation" "Copilot session ended: ${REASON}" \
      "{\"source\": \"copilot\", \"reason\": \"${REASON}\"}"
    om_end_session
    ;;

  userPromptSubmitted)
    PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || echo "")
    [ -z "$PROMPT" ] && exit 0
    _om_load_session
    om_observe "user_prompt" "$PROMPT" '{"source": "copilot"}'
    ;;

  postToolUse)
    TOOL=$(echo "$INPUT" | jq -r '.toolName // empty' 2>/dev/null || echo "")
    TOOL_ARGS=$(echo "$INPUT" | jq -r '.toolArgs // empty' 2>/dev/null || echo "")
    RESULT_TYPE=$(echo "$INPUT" | jq -r '.toolResult.resultType // empty' 2>/dev/null || echo "")
    [ -z "$TOOL" ] && exit 0
    _om_load_session
    om_observe "tool_use" "Copilot tool: ${TOOL} (${RESULT_TYPE})" \
      "{\"source\": \"copilot\", \"tool\": \"${TOOL}\"}"
    ;;

  errorOccurred)
    ERROR_MSG=$(echo "$INPUT" | jq -r '.error.message // empty' 2>/dev/null || echo "")
    ERROR_NAME=$(echo "$INPUT" | jq -r '.error.name // empty' 2>/dev/null || echo "")
    _om_load_session
    om_observe "observation" "Copilot error: ${ERROR_NAME}: ${ERROR_MSG}" \
      "{\"source\": \"copilot\", \"error\": \"${ERROR_NAME}\"}"
    ;;

  *)
    # Unknown event — ignore
    ;;
esac

exit 0
