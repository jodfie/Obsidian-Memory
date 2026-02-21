#!/usr/bin/env bash
# Cline TaskCancel hook — ends OM session on cancellation
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/om-hook-common.sh"

_OM_SOURCE="cline"
_OM_SESSION_FILE="/tmp/obsidian-memory-cline-session.json"

INPUT=$(cat 2>/dev/null || echo '{}')
TASK_ID=$(echo "$INPUT" | jq -r '.taskId // empty' 2>/dev/null || echo "")

_om_load_session
om_observe "observation" "Cline task cancelled" "{\"source\": \"cline\", \"task_id\": \"${TASK_ID}\"}"
om_end_session
exit 0
