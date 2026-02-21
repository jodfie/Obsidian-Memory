#!/usr/bin/env bash
# Cline PostToolUse hook — logs tool usage
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/om-hook-common.sh"

_OM_SOURCE="cline"
_OM_SESSION_FILE="/tmp/obsidian-memory-cline-session.json"

INPUT=$(cat 2>/dev/null || echo '{}')
TOOL=$(echo "$INPUT" | jq -r '.tool // empty' 2>/dev/null || echo "")
SUCCESS=$(echo "$INPUT" | jq -r '.success // empty' 2>/dev/null || echo "")
DURATION=$(echo "$INPUT" | jq -r '.durationMs // empty' 2>/dev/null || echo "")
PARAMS=$(echo "$INPUT" | jq -c '.parameters // {}' 2>/dev/null || echo '{}')

[ -z "$TOOL" ] && exit 0

_om_load_session
om_observe "tool_use" "Cline tool: ${TOOL} (success=${SUCCESS}, ${DURATION}ms)" \
  "{\"source\": \"cline\", \"tool\": \"${TOOL}\", \"success\": ${SUCCESS:-true}, \"duration_ms\": ${DURATION:-0}}"
exit 0
