#!/usr/bin/env bash
# setup-remote-om.sh — Set up Obsidian-Memory hooks and CLI tools on a remote machine
#
# This script is designed to be run ON the remote machine (via SSH or locally).
# It installs Claude Code, Codex, and Happy if missing, then deploys OM hooks
# so every Claude Code session reports back to the OM API over Tailscale.
#
# Quick install (from any machine with curl):
#   OM_HOST=my-server bash -c "$(curl -fsSL https://raw.githubusercontent.com/jodfie/Obsidian-Memory/main/scripts/setup-remote-om.sh)"
#
# Other usage:
#   OM_HOST=my-server ./scripts/setup-remote-om.sh              # run locally from repo
#   ssh user@host 'OM_HOST=my-server bash -s' < scripts/setup-remote-om.sh  # pipe via SSH
#
# Environment variables:
#   OM_HOST      - Tailscale MagicDNS hostname of the OM server (REQUIRED)
#   OM_API_PORT  - OM API port (default: 8765)

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────
OM_HOST="${OM_HOST:?OM_HOST must be set to your OM server Tailscale hostname (e.g. my-server)}"
OM_API_PORT="${OM_API_PORT:-8765}"
OM_API_URL="http://${OM_HOST}:${OM_API_PORT}"

CLAUDE_DIR="$HOME/.claude"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SCRIPTS_DIR="$CLAUDE_DIR/scripts"

# ── Helpers ──────────────────────────────────────────────────────────
info()  { echo "  [INFO]  $*"; }
ok()    { echo "  [OK]    $*"; }
warn()  { echo "  [WARN]  $*"; }
err()   { echo "  [ERROR] $*" >&2; }
step()  { echo ""; echo "── $* ──"; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# ── Pre-flight checks ───────────────────────────────────────────────
step "Pre-flight checks"

if ! command_exists tailscale; then
  err "Tailscale is not installed. Install it first: https://tailscale.com/download"
  exit 1
fi

TS_IP=$(tailscale ip -4 2>/dev/null || echo "")
if [ -z "$TS_IP" ]; then
  err "Tailscale is installed but not connected. Run: sudo tailscale up"
  exit 1
fi
ok "Tailscale connected at $TS_IP"

# Check connectivity to OM host
if curl -sf --connect-timeout 3 --max-time 5 "${OM_API_URL}/health" >/dev/null 2>&1; then
  ok "OM API reachable at ${OM_API_URL}"
else
  warn "OM API not reachable at ${OM_API_URL} — hooks will silently no-op until it's available"
fi

# ── Ensure Node.js ───────────────────────────────────────────────────
step "Checking Node.js"

if command_exists node; then
  NODE_VERSION=$(node --version 2>/dev/null)
  NODE_MAJOR=$(echo "$NODE_VERSION" | sed 's/v\([0-9]*\).*/\1/')
  if [ "$NODE_MAJOR" -ge 20 ]; then
    ok "Node.js $NODE_VERSION (>= 20 required)"
  else
    warn "Node.js $NODE_VERSION is too old (>= 20 required)"
    info "Install Node 22: curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs"
    info "Or use nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash && nvm install 22"
    exit 1
  fi
else
  warn "Node.js not found"
  info "Install Node 22: curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs"
  exit 1
fi

# ── Install Claude Code ─────────────────────────────────────────────
step "Checking Claude Code"

if command_exists claude; then
  ok "Claude Code $(claude --version 2>/dev/null || echo 'installed')"
else
  info "Installing Claude Code via npm..."
  npm install -g @anthropic-ai/claude-code 2>/dev/null || {
    warn "npm global install failed, trying with sudo..."
    sudo npm install -g @anthropic-ai/claude-code 2>/dev/null || true
  }
  # Ensure it's in PATH for the rest of this script
  export PATH="$HOME/.local/bin:$PATH"
  if command_exists claude; then
    ok "Claude Code installed: $(claude --version 2>/dev/null)"
  else
    err "Claude Code installation failed"
    info "Try manually: npm install -g @anthropic-ai/claude-code"
    exit 1
  fi
fi

# ── Install Codex ────────────────────────────────────────────────────
step "Checking Codex"

if command_exists codex; then
  ok "Codex $(codex --version 2>/dev/null || echo 'installed')"
else
  info "Installing Codex..."
  npm install -g @openai/codex 2>/dev/null || {
    warn "Codex install failed (may need sudo or different npm prefix)"
    info "Manual install: npm install -g @openai/codex"
  }
  if command_exists codex; then
    ok "Codex installed"
  else
    warn "Codex not in PATH — may need a new shell"
  fi
fi

# ── Install Happy ────────────────────────────────────────────────────
step "Checking Happy"

if command_exists happy; then
  ok "Happy $(happy --version 2>/dev/null || echo 'installed')"
else
  info "Installing Happy..."
  npm install -g happy-coder 2>/dev/null || {
    warn "Happy install failed (may need sudo or different npm prefix)"
    info "Manual install: npm install -g happy-coder"
  }
  if command_exists happy; then
    ok "Happy installed"
  else
    warn "Happy not in PATH — may need a new shell"
  fi
fi

# ── Deploy OM hooks ──────────────────────────────────────────────────
step "Deploying OM hooks to ${HOOKS_DIR}"

mkdir -p "$HOOKS_DIR" "$SCRIPTS_DIR"

# ── _lib.sh (shared library for all hooks) ──
cat > "$HOOKS_DIR/_lib.sh" << 'HOOKEOF'
#!/usr/bin/env bash
# _lib.sh -- Shared functions for Obsidian-Memory Claude Code hooks
source "$(dirname "$0")/_lib.sh" 2>/dev/null && return 0 || true

set -euo pipefail

API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
SESSION_FILE="/tmp/obsidian-memory-session.json"
_HOOK_WARNINGS=()

SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-}"
if [ -z "$SESSION_ID" ] && [ -f "$SESSION_FILE" ]; then
  SESSION_ID=$(jq -r '.session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
  API_URL=$(jq -r '.api_url // empty' "$SESSION_FILE" 2>/dev/null || echo "$API_URL")
fi

INPUT=""
read_input() {
  INPUT=$(cat 2>/dev/null || echo '{}')
  if ! echo "$INPUT" | jq empty 2>/dev/null; then INPUT='{}'; fi
}

field() { echo "$INPUT" | jq -r ".$1 // empty" 2>/dev/null || echo ""; }

hook_warn() {
  local msg="$1"
  _HOOK_WARNINGS+=("$msg")
  echo "[obsidian-memory] WARNING: $msg" >&2
}

emit_warnings() {
  if [ ${#_HOOK_WARNINGS[@]} -eq 0 ]; then return; fi
  local joined=""
  for w in "${_HOOK_WARNINGS[@]}"; do
    [ -n "$joined" ] && joined="$joined; "
    joined="$joined$w"
  done
  jq -n --arg ctx "[OM] $joined" '{
    hookSpecificOutput: { hookEventName: "ObsidianMemory", additionalContext: $ctx }
  }'
}

require_session() {
  if [ -z "$SESSION_ID" ]; then
    hook_warn "No OM session active. Session tracking disabled."
    emit_warnings
    exit 0
  fi
}

_API_HTTP_CODE=""
api_get() {
  local response
  _API_HTTP_CODE=""
  response=$(curl -s --connect-timeout 2 --max-time 5 -w "\n%{http_code}" \
    -H "Content-Type: application/json" "${API_URL}/$1" 2>/dev/null) || { echo ""; return 1; }
  _API_HTTP_CODE=$(echo "$response" | tail -1)
  echo "$response" | sed '$d'
}

api_post() {
  local endpoint="$1" data="$2" response
  _API_HTTP_CODE=""
  response=$(curl -s --connect-timeout 2 --max-time 5 -w "\n%{http_code}" \
    -X POST -H "Content-Type: application/json" -d "$data" \
    "${API_URL}/${endpoint}" 2>/dev/null) || { echo ""; return 1; }
  _API_HTTP_CODE=$(echo "$response" | tail -1)
  echo "$response" | sed '$d'
}

is_backend_up() {
  curl -sf --connect-timeout 2 --max-time 3 "${API_URL}/health" >/dev/null 2>&1
}

validate_session() {
  [ -z "$SESSION_ID" ] && return 1
  api_get "api/sessions/${SESSION_ID}" >/dev/null
  [ "$_API_HTTP_CODE" = "200" ]
}

recreate_session() {
  local project="${1:-}" claude_session_id="${2:-$SESSION_ID}"
  local response new_id
  response=$(api_post "api/sessions" "{\"session_id\": \"${claude_session_id}\", \"project\": \"${project}\"}")
  new_id=$(echo "$response" | jq -r '.session_id // empty' 2>/dev/null || echo "")
  if [ -z "$new_id" ]; then
    hook_warn "Failed to create OM session (HTTP ${_API_HTTP_CODE})"
    return 1
  fi
  SESSION_ID="$new_id"
  jq -n --arg sid "$new_id" --arg csid "$claude_session_id" --arg url "$API_URL" --arg proj "$project" \
    '{session_id: $sid, claude_session_id: $csid, api_url: $url, project: $proj}' > "$SESSION_FILE"
  if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export OBSIDIAN_MEMORY_SESSION_ID=\"${new_id}\"" >> "$CLAUDE_ENV_FILE"
    echo "export OBSIDIAN_MEMORY_API_URL=\"${API_URL}\"" >> "$CLAUDE_ENV_FILE"
    echo "export OBSIDIAN_MEMORY_PROJECT=\"${project}\"" >> "$CLAUDE_ENV_FILE"
  fi
}

observe_event() {
  local event_type="$1" content="$2" metadata="${3:-\{\}}"
  local escaped_content
  escaped_content=$(echo "$content" | jq -Rs '.' 2>/dev/null || echo "\"$content\"")
  api_post "api/sessions/observe" "{
    \"session_id\": \"${SESSION_ID}\",
    \"event_type\": \"${event_type}\",
    \"content\": ${escaped_content},
    \"metadata\": ${metadata}
  }" >/dev/null 2>&1
  if [ "$_API_HTTP_CODE" != "200" ] && [ "$_API_HTTP_CODE" != "201" ]; then
    if [ "$_API_HTTP_CODE" = "404" ]; then
      hook_warn "Session ${SESSION_ID} not found (observation lost)"
    elif [ -z "$_API_HTTP_CODE" ]; then
      hook_warn "OM API unreachable (observation lost)"
    fi
  fi
}
HOOKEOF
chmod +x "$HOOKS_DIR/_lib.sh"

# ── session-start.sh ──
cat > "$HOOKS_DIR/session-start.sh" << 'HOOKEOF'
#!/usr/bin/env bash
# session-start.sh -- validates existing sessions, re-creates if stale
source "$(dirname "$0")/_lib.sh"
read_input

CLAUDE_SESSION_ID=$(field "session_id")

if ! is_backend_up; then
  hook_warn "OM API unreachable at ${API_URL}. Session tracking disabled."
  emit_warnings
  exit 0
fi

if [ -f "$SESSION_FILE" ]; then
  EXISTING_CSID=$(jq -r '.claude_session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
  if [ "$EXISTING_CSID" = "$CLAUDE_SESSION_ID" ]; then
    BACKEND_SESSION_ID=$(jq -r '.session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
    SESSION_ID="$BACKEND_SESSION_ID"
    if validate_session; then
      PROJECT=$(jq -r '.project // empty' "$SESSION_FILE" 2>/dev/null || echo "")
      jq -n --arg ctx "Obsidian-Memory session active: ${BACKEND_SESSION_ID} (project: ${PROJECT})" '{
        hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: $ctx }
      }'
      exit 0
    else
      hook_warn "Session ${BACKEND_SESSION_ID} stale (backend restart?). Re-creating."
      rm -f "$SESSION_FILE"
    fi
  else
    rm -f "$SESSION_FILE"
  fi
fi

SOURCE=$(field "source")
MODEL=$(field "model")
CWD=$(field "cwd")
PROJECT=$(basename "$CWD" 2>/dev/null || echo "")

if recreate_session "$PROJECT" "$CLAUDE_SESSION_ID"; then
  observe_event "observation" "Session started: model=${MODEL}, source=${SOURCE}, project=${PROJECT}" \
    "{\"model\": \"${MODEL}\", \"source\": \"${SOURCE}\", \"project\": \"${PROJECT}\"}"
  jq -n --arg ctx "Obsidian-Memory session created: ${SESSION_ID} (project: ${PROJECT})" '{
    hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: $ctx }
  }'
else
  emit_warnings
fi
exit 0
HOOKEOF
chmod +x "$HOOKS_DIR/session-start.sh"

# ── session-end.sh ──
cat > "$HOOKS_DIR/session-end.sh" << 'HOOKEOF'
#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
read_input
require_session

api_post "api/sessions/${SESSION_ID}/end" '{}' >/dev/null 2>&1
if [ "$_API_HTTP_CODE" != "200" ] && [ -n "$_API_HTTP_CODE" ]; then
  echo "[obsidian-memory] WARNING: Session end failed (HTTP ${_API_HTTP_CODE})" >&2
fi
rm -f "$SESSION_FILE"
exit 0
HOOKEOF
chmod +x "$HOOKS_DIR/session-end.sh"

# ── user-prompt-submit.sh ──
cat > "$HOOKS_DIR/user-prompt-submit.sh" << 'HOOKEOF'
#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
read_input
require_session

PROMPT=$(field "prompt")
[ -z "$PROMPT" ] && exit 0

observe_event "user_prompt" "$PROMPT"
exit 0
HOOKEOF
chmod +x "$HOOKS_DIR/user-prompt-submit.sh"

# ── post-tool-use-edits.sh ──
cat > "$HOOKS_DIR/post-tool-use-edits.sh" << 'HOOKEOF'
#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
read_input
require_session

TOOL=$(field "tool_name")
FILE_PATH=$(field "file_path")
[ -z "$TOOL" ] && exit 0

observe_event "tool_use" "Edit: ${TOOL} on ${FILE_PATH}" \
  "{\"tool\": \"${TOOL}\", \"file_path\": \"${FILE_PATH}\"}"
exit 0
HOOKEOF
chmod +x "$HOOKS_DIR/post-tool-use-edits.sh"

# ── post-tool-use-search.sh ──
cat > "$HOOKS_DIR/post-tool-use-search.sh" << 'HOOKEOF'
#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
read_input
require_session

TOOL=$(field "tool_name")
QUERY=$(field "pattern")
[ -z "$TOOL" ] && exit 0

observe_event "tool_use" "Search: ${TOOL} for ${QUERY}" \
  "{\"tool\": \"${TOOL}\", \"query\": \"${QUERY}\"}"
exit 0
HOOKEOF
chmod +x "$HOOKS_DIR/post-tool-use-search.sh"

# ── pre-compact.sh ──
cat > "$HOOKS_DIR/pre-compact.sh" << 'HOOKEOF'
#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
read_input
require_session

if ! is_backend_up; then
  hook_warn "OM API unreachable before compaction. Session context will be lost!"
  emit_warnings
  exit 0
fi

api_post "api/sessions/${SESSION_ID}/summary" '{"trigger": "pre_compact"}' >/dev/null 2>&1 || true
exit 0
HOOKEOF
chmod +x "$HOOKS_DIR/pre-compact.sh"

# ── stop.sh ──
cat > "$HOOKS_DIR/stop.sh" << 'HOOKEOF'
#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
read_input
require_session

if ! is_backend_up; then
  hook_warn "OM API unreachable at stop. Session summary skipped."
  emit_warnings
  exit 0
fi

REASON=$(field "reason")
observe_event "observation" "Session stopped: ${REASON}" \
  "{\"reason\": \"${REASON}\"}"

api_post "api/sessions/${SESSION_ID}/summary" '{"trigger": "stop"}' >/dev/null 2>&1 || true
exit 0
HOOKEOF
chmod +x "$HOOKS_DIR/stop.sh"

ok "Hooks deployed to $HOOKS_DIR"

# ── Deploy om.sh ─────────────────────────────────────────────────────
step "Deploying om.sh CLI helper"

cat > "$SCRIPTS_DIR/om.sh" << 'OMEOF'
#!/usr/bin/env bash
# om.sh — Obsidian-Memory CLI helper
# Usage: om.sh write --title "T" --content "C" [--project P] [--type T] [--tags t1,t2]
#        om.sh search "query" [--project P] [--limit N]
#        om.sh read --id 123 | --permalink "slug"
#        om.sh update --id 123 --content "C" [--title "T"]
#        om.sh delete --id 123
#        om.sh supersede --old 123 --new 456 [--reason "why"]
#        om.sh projects | om.sh health

set -euo pipefail

API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
SESSION_FILE="/tmp/obsidian-memory-session.json"

if [ -f "$SESSION_FILE" ]; then
  SAVED_URL=$(jq -r '.api_url // empty' "$SESSION_FILE" 2>/dev/null || echo "")
  [ -n "$SAVED_URL" ] && API_URL="$SAVED_URL"
fi

die() { echo "ERROR: $*" >&2; exit 1; }

api() {
  local method="$1" endpoint="$2"
  shift 2
  curl -sf --connect-timeout 3 --max-time 30 \
    -X "$method" \
    -H "Content-Type: application/json" \
    "$@" \
    "${API_URL}/${endpoint}" 2>/dev/null
}

CMD="${1:-help}"
shift || true

case "$CMD" in
  health)
    api GET "health" | jq .
    ;;
  projects)
    api GET "api/projects" | jq .
    ;;
  search)
    QUERY="${1:-}"
    shift || true
    [ -z "$QUERY" ] && die "Usage: om.sh search \"query\" [--project P] [--limit N]"
    PROJECT="" LIMIT="10" TAGS="" TYPE=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --project) PROJECT="$2"; shift 2 ;;
        --limit) LIMIT="$2"; shift 2 ;;
        --tags) TAGS="$2"; shift 2 ;;
        --type) TYPE="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    PARAMS="q=$(printf '%s' "$QUERY" | jq -sRr @uri)&limit=${LIMIT}"
    [ -n "$PROJECT" ] && PARAMS="${PARAMS}&project=${PROJECT}"
    [ -n "$TAGS" ] && PARAMS="${PARAMS}&tags=${TAGS}"
    [ -n "$TYPE" ] && PARAMS="${PARAMS}&type=${TYPE}"
    api GET "api/notes/search?${PARAMS}" | jq .
    ;;
  read)
    ID="" PERMALINK=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --id) ID="$2"; shift 2 ;;
        --permalink) PERMALINK="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    if [ -n "$ID" ]; then
      api GET "api/notes/${ID}" | jq .
    elif [ -n "$PERMALINK" ]; then
      api GET "api/notes/permalink/${PERMALINK}" | jq .
    else
      die "Usage: om.sh read --id 123 | --permalink \"slug\""
    fi
    ;;
  write)
    TITLE="" CONTENT="" PROJECT="" TYPE="note" TAGS="" NOTE_PATH=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --title) TITLE="$2"; shift 2 ;;
        --content) CONTENT="$2"; shift 2 ;;
        --project) PROJECT="$2"; shift 2 ;;
        --type) TYPE="$2"; shift 2 ;;
        --tags) TAGS="$2"; shift 2 ;;
        --path) NOTE_PATH="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    [ -z "$TITLE" ] && die "Usage: om.sh write --title \"T\" --content \"C\" [--project P] [--type T] [--tags t1,t2]"
    PAYLOAD=$(jq -n \
      --arg title "$TITLE" \
      --arg content "$CONTENT" \
      --arg project "$PROJECT" \
      --arg type "$TYPE" \
      --arg tags "$TAGS" \
      --arg path "$NOTE_PATH" \
      '{title: $title, content: $content} +
       (if $project != "" then {project: $project} else {} end) +
       (if $type != "" then {type: $type} else {} end) +
       (if $tags != "" then {tags: ($tags | split(","))} else {} end) +
       (if $path != "" then {path: $path} else {} end)')
    api POST "api/notes" -d "$PAYLOAD" | jq .
    ;;
  update)
    ID="" TITLE="" CONTENT=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --id) ID="$2"; shift 2 ;;
        --title) TITLE="$2"; shift 2 ;;
        --content) CONTENT="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    [ -z "$ID" ] && die "Usage: om.sh update --id 123 --content \"C\" [--title \"T\"]"
    PAYLOAD=$(jq -n \
      --arg title "$TITLE" \
      --arg content "$CONTENT" \
      '(if $title != "" then {title: $title} else {} end) +
       (if $content != "" then {content: $content} else {} end)')
    api PUT "api/notes/${ID}" -d "$PAYLOAD" | jq .
    ;;
  delete)
    ID=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --id) ID="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    [ -z "$ID" ] && die "Usage: om.sh delete --id 123"
    api DELETE "api/notes/${ID}" | jq .
    ;;
  supersede)
    OLD="" NEW="" REASON=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --old) OLD="$2"; shift 2 ;;
        --new) NEW="$2"; shift 2 ;;
        --reason) REASON="$2"; shift 2 ;;
        *) shift ;;
      esac
    done
    [ -z "$OLD" ] || [ -z "$NEW" ] && die "Usage: om.sh supersede --old 123 --new 456 [--reason \"why\"]"
    PAYLOAD=$(jq -n \
      --arg new_id "$NEW" \
      --arg reason "$REASON" \
      '{new_note_id: ($new_id | tonumber)} +
       (if $reason != "" then {reason: $reason} else {} end)')
    api POST "api/notes/${OLD}/supersede" -d "$PAYLOAD" | jq .
    ;;
  help|*)
    echo "om.sh — Obsidian-Memory CLI helper"
    echo ""
    echo "Commands:"
    echo "  write    --title T --content C [--project P] [--type T] [--tags t1,t2]"
    echo "  read     --id 123 | --permalink slug"
    echo "  search   \"query\" [--project P] [--limit N]"
    echo "  update   --id 123 --content C [--title T]"
    echo "  delete   --id 123"
    echo "  supersede --old 123 --new 456 [--reason why]"
    echo "  projects"
    echo "  health"
    ;;
esac
OMEOF
chmod +x "$SCRIPTS_DIR/om.sh"
ok "om.sh deployed to $SCRIPTS_DIR/om.sh"

# ── Set environment variable ─────────────────────────────────────────
step "Configuring environment"

SHELL_RC="$HOME/.bashrc"
if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "$SHELL" 2>/dev/null)" = "zsh" ]; then
  SHELL_RC="$HOME/.zshrc"
fi

if grep -q "OBSIDIAN_MEMORY_API_URL" "$SHELL_RC" 2>/dev/null; then
  # Update existing
  sed -i "s|export OBSIDIAN_MEMORY_API_URL=.*|export OBSIDIAN_MEMORY_API_URL=\"${OM_API_URL}\"|" "$SHELL_RC"
  ok "Updated OBSIDIAN_MEMORY_API_URL in $SHELL_RC"
else
  echo "" >> "$SHELL_RC"
  echo "# Obsidian-Memory API (via Tailscale)" >> "$SHELL_RC"
  echo "export OBSIDIAN_MEMORY_API_URL=\"${OM_API_URL}\"" >> "$SHELL_RC"
  ok "Added OBSIDIAN_MEMORY_API_URL to $SHELL_RC"
fi

# ── Configure Claude Code hooks in settings ──────────────────────────
step "Configuring Claude Code hook settings"

SETTINGS_DIR="$HOME/.claude"
SETTINGS_FILE="$SETTINGS_DIR/settings.json"
mkdir -p "$SETTINGS_DIR"

# Create or update settings.json with hook configuration
if [ -f "$SETTINGS_FILE" ]; then
  # Merge hooks into existing settings
  EXISTING=$(cat "$SETTINGS_FILE")
  echo "$EXISTING" | jq '.hooks = {
    "SessionStart": [{"matcher": "startup|resume", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/session-start.sh"}]}],
    "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/user-prompt-submit.sh"}]}],
    "PostToolUse": [
      {"matcher": "Edit|Write|NotebookEdit", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/post-tool-use-edits.sh"}]},
      {"matcher": "Grep|Glob|WebSearch", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/post-tool-use-search.sh"}]}
    ],
    "PreCompact": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/pre-compact.sh"}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/stop.sh"}]}],
    "SessionEnd": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/session-end.sh"}]}]
  }' > "$SETTINGS_FILE"
  ok "Merged hooks into existing $SETTINGS_FILE"
else
  jq -n '{
    "hooks": {
      "SessionStart": [{"matcher": "startup|resume", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/session-start.sh"}]}],
      "UserPromptSubmit": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/user-prompt-submit.sh"}]}],
      "PostToolUse": [
        {"matcher": "Edit|Write|NotebookEdit", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/post-tool-use-edits.sh"}]},
        {"matcher": "Grep|Glob|WebSearch", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/post-tool-use-search.sh"}]}
      ],
      "PreCompact": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/pre-compact.sh"}]}],
      "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/stop.sh"}]}],
      "SessionEnd": [{"matcher": "", "hooks": [{"type": "command", "command": "'"$HOOKS_DIR"'/session-end.sh"}]}]
    }
  }' > "$SETTINGS_FILE"
  ok "Created $SETTINGS_FILE with hook configuration"
fi

# ── Summary ──────────────────────────────────────────────────────────
step "Setup complete!"
echo ""
echo "  Tailscale IP:  $TS_IP"
echo "  OM API URL:    $OM_API_URL"
echo "  Hooks:         $HOOKS_DIR/"
echo "  om.sh:         $SCRIPTS_DIR/om.sh"
echo "  Shell RC:      $SHELL_RC"
echo ""
echo "  Next steps:"
echo "    1. Open a new shell (or: source $SHELL_RC)"
echo "    2. Test: $SCRIPTS_DIR/om.sh health"
echo "    3. Start Claude Code — hooks will auto-connect to OM"
echo ""
