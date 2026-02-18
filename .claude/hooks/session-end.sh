#!/usr/bin/env bash
# session-end.sh — SessionEnd hook (async)
# Ends the Obsidian-Memory session with auto-summarization and cleans up session file.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

REASON=$(field "reason")

# End the session (backend will auto-summarize if threshold met)
api_post "api/sessions/${SESSION_ID}/end" "{\"auto_summarize\": true}" >/dev/null 2>&1 || true

# Clean up session file
rm -f "$SESSION_FILE" 2>/dev/null || true

exit 0
