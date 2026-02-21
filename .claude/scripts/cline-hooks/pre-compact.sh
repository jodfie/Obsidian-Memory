#!/usr/bin/env bash
# Cline PreCompact hook — triggers OM summary before context truncation
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$SCRIPT_DIR/om-hook-common.sh"

_OM_SOURCE="cline"
_OM_SESSION_FILE="/tmp/obsidian-memory-cline-session.json"

INPUT=$(cat 2>/dev/null || echo '{}')
TOKENS=$(echo "$INPUT" | jq -r '.estimatedTokens // empty' 2>/dev/null || echo "")

_om_load_session
om_observe "observation" "Cline pre-compact (est. ${TOKENS} tokens)" '{"source": "cline"}'
om_summarize

# Inject context back into Cline conversation
echo '{"contextModification": "[OM] Session summarized before compaction."}'
exit 0
