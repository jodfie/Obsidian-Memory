#!/usr/bin/env bash
# session-end.sh — SessionEnd hook (async)
# Ends the Obsidian-Memory session with auto-summarization and cleans up session file.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

REASON=$(field "reason")

# End the session (backend will auto-summarize if threshold met)
api_post "api/sessions/${SESSION_ID}/end" "{\"auto_summarize\": true}" >/dev/null 2>&1
if [ "$_API_HTTP_CODE" != "200" ] && [ -n "$_API_HTTP_CODE" ]; then
  echo "[obsidian-memory] WARNING: Session end failed (HTTP ${_API_HTTP_CODE}). Session ${SESSION_ID} may be orphaned." >&2
fi

# Clean up session file
rm -f "$SESSION_FILE" 2>/dev/null || true

exit 0
