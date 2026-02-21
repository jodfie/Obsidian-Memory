#!/usr/bin/env bash
# session-start.sh — SessionStart hook (sync, matcher: startup|resume)
# Creates a new Obsidian-Memory session and persists state via session file + CLAUDE_ENV_FILE.
# Validates existing sessions on the backend and re-creates if stale.

source "$(dirname "$0")/_lib.sh"
read_input

CLAUDE_SESSION_ID=$(field "session_id")

# ── Check backend first ──
if ! is_backend_up; then
  hook_warn "OM API unreachable at ${API_URL}. Session tracking disabled until backend is available."
  emit_warnings
  exit 0
fi

# ── Check for hook updates (non-blocking) ──
check_hook_version

# ── If session file exists, validate it ──
if [ -f "$SESSION_FILE" ]; then
  EXISTING_CSID=$(jq -r '.claude_session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")

  if [ "$EXISTING_CSID" = "$CLAUDE_SESSION_ID" ]; then
    # Same Claude session — validate the backend session still exists
    BACKEND_SESSION_ID=$(jq -r '.session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
    SESSION_ID="$BACKEND_SESSION_ID"

    if validate_session; then
      # Session is valid on backend — return cached context
      PROJECT=$(jq -r '.project // empty' "$SESSION_FILE" 2>/dev/null || echo "")
      jq -n --arg ctx "Obsidian-Memory session active: ${BACKEND_SESSION_ID} (project: ${PROJECT})" '{
        hookSpecificOutput: {
          hookEventName: "SessionStart",
          additionalContext: $ctx
        }
      }'
      exit 0
    else
      # Session is stale — re-create it
      hook_warn "Session ${BACKEND_SESSION_ID} no longer exists on backend (container restart?). Re-creating."
      rm -f "$SESSION_FILE"
    fi
  else
    # Different Claude session — clean up old file
    rm -f "$SESSION_FILE"
  fi
fi

# ── Extract fields for new session ──
SOURCE=$(field "source")
MODEL=$(field "model")
CWD=$(field "cwd")
PROJECT=$(basename "$CWD" 2>/dev/null || echo "")

# ── Create session ──
if recreate_session "$PROJECT" "$CLAUDE_SESSION_ID"; then
  observe_event "observation" "Session started: model=${MODEL}, source=${SOURCE}, project=${PROJECT}" \
    "{\"model\": \"${MODEL}\", \"source\": \"${SOURCE}\", \"project\": \"${PROJECT}\"}"

  jq -n --arg ctx "Obsidian-Memory session created: ${SESSION_ID} (project: ${PROJECT})" '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: $ctx
    }
  }'
else
  emit_warnings
fi

exit 0
