#!/usr/bin/env bash
# Cline TaskComplete hook — ends OM session with summary
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/om-hook-common.sh"

_OM_SOURCE="cline"
_OM_SESSION_FILE="/tmp/obsidian-memory-cline-session.json"

INPUT=$(cat 2>/dev/null || echo '{}')
TASK_ID=$(echo "$INPUT" | jq -r '.taskId // empty' 2>/dev/null || echo "")

_om_load_session
om_observe "observation" "Cline task completed" "{\"source\": \"cline\", \"task_id\": \"${TASK_ID}\"}"
om_end_session
exit 0
