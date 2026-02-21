#!/usr/bin/env bash
# Cline UserPromptSubmit hook — logs user prompts
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/om-hook-common.sh"

_OM_SOURCE="cline"
_OM_SESSION_FILE="/tmp/obsidian-memory-cline-session.json"

INPUT=$(cat 2>/dev/null || echo '{}')
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || echo "")
[ -z "$PROMPT" ] && exit 0

_om_load_session
om_observe "user_prompt" "$PROMPT" '{"source": "cline"}'
exit 0
