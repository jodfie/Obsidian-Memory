#!/usr/bin/env bash
# pre-compact.sh — PreCompact hook (sync)
# Triggers session summarization before context is lost to compaction.

source "$(dirname "$0")/_lib.sh"
read_input
require_session

if ! is_backend_up; then
  hook_warn "OM API unreachable before compaction. Session context will be lost!"
  emit_warnings
  exit 0
fi

TRIGGER=$(field "trigger")

echo "[obsidian-memory] PreCompact (${TRIGGER}): Triggering session summarization..." >&2

# Trigger incremental summary with longer timeout
RESPONSE=$(curl -sf --connect-timeout 5 --max-time 25 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"force_incremental": true}' \
  "${API_URL}/api/sessions/${SESSION_ID}/summary" 2>/dev/null || echo "")

if echo "$RESPONSE" | jq -e '.key_learnings' >/dev/null 2>&1; then
  echo "[obsidian-memory] Session summarized successfully before compaction" >&2
else
  echo "[obsidian-memory] WARNING: Summarization may have failed or AI unavailable" >&2
fi

exit 0
