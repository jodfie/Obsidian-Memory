#!/usr/bin/env bash
# session-end.sh — SessionEnd hook (async)
# Ends the Obsidian-Memory session with auto-summarization.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

REASON=$(field "reason")

# End the session (backend will auto-summarize if threshold met)
api_post "api/sessions/${SESSION_ID}/end" "{\"auto_summarize\": true}" >/dev/null 2>&1 || true

exit 0
