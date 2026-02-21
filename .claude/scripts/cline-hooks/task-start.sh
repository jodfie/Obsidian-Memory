#!/usr/bin/env bash
# Cline TaskStart hook — creates OM session for this task
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/om-hook-common.sh"

_OM_SOURCE="cline"
_OM_SESSION_FILE="/tmp/obsidian-memory-cline-session.json"

INPUT=$(cat 2>/dev/null || echo '{}')
TASK_ID=$(echo "$INPUT" | jq -r '.taskId // empty' 2>/dev/null || echo "")
WORKSPACE=$(echo "$INPUT" | jq -r '.workspacePath // empty' 2>/dev/null || echo "")
TASK=$(echo "$INPUT" | jq -r '.task // empty' 2>/dev/null || echo "")
PROJECT=$(basename "$WORKSPACE" 2>/dev/null || echo "")

om_session_ensure "$TASK_ID" "$PROJECT"
om_observe "observation" "Cline task started: ${TASK:0:200}" \
  "{\"source\": \"cline\", \"task_id\": \"${TASK_ID}\", \"project\": \"${PROJECT}\"}"
exit 0
