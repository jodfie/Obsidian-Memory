#!/usr/bin/env bash
# Log a session observation to Obsidian-Memory
# Usage: ./session_log.sh <session_id> <event_type> <content>

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

SESSION_ID="${1:?Usage: session_log.sh <session_id> <event_type> <content>}"
EVENT_TYPE="${2:?Event type required: observation|decision|error|solution|tool_use|file_edit|command|research|user_prompt}"
CONTENT="${3:?Content is required}"

RESPONSE=$(mem_session_observe "$SESSION_ID" "$EVENT_TYPE" "$CONTENT")

echo "$RESPONSE" | check_error | jq -r '
    if .id then
        "Event logged:\n  Session: \(.session_id // "unknown")\n  Type: \(.event_type)\n  ID: \(.id)"
    else
        "Event logged successfully."
    end
'
