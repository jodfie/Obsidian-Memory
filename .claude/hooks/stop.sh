#!/usr/bin/env bash
# stop.sh — Stop hook (sync)
# Ensures session has a summary before Claude stops. Never blocks stop.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

# Prevent infinite loops — if stop hook already active, exit immediately
STOP_HOOK_ACTIVE=$(field "stop_hook_active")
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

if ! is_backend_up; then
  exit 0
fi

# Check current session state
SESSION_INFO=$(api_get "api/sessions/${SESSION_ID}")
if [ -z "$SESSION_INFO" ]; then
  exit 0
fi

EVENT_COUNT=$(echo "$SESSION_INFO" | jq -r '.event_count // 0' 2>/dev/null || echo "0")

# If session has enough events, trigger a summary (fire-and-forget)
if [ "$EVENT_COUNT" -gt 5 ]; then
  api_post "api/sessions/${SESSION_ID}/summary" '{}' >/dev/null 2>&1 || true
fi

exit 0
