#!/usr/bin/env bash
# _lib.sh — Shared functions for Obsidian-Memory Claude Code hooks
# Source this file at the top of each hook: source "$(dirname "$0")/_lib.sh"

set -euo pipefail

# ── Version ─────────────────────────────────────────────────────────
OM_HOOKS_VERSION="2"

# ── Config ──────────────────────────────────────────────────────────
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
SESSION_FILE="/tmp/obsidian-memory-session.json"
_VERSION_CHECK_FILE="/tmp/obsidian-memory-version-checked"
_HOOK_WARNINGS=()

# Load session ID: env var first, then session file fallback
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-}"
if [ -z "$SESSION_ID" ] && [ -f "$SESSION_FILE" ]; then
  SESSION_ID=$(jq -r '.session_id // empty' "$SESSION_FILE" 2>/dev/null || echo "")
  API_URL=$(jq -r '.api_url // empty' "$SESSION_FILE" 2>/dev/null || echo "$API_URL")
fi

# ── Input parsing ───────────────────────────────────────────────────
INPUT=""
read_input() {
  INPUT=$(cat 2>/dev/null || echo '{}')
  if ! echo "$INPUT" | jq empty 2>/dev/null; then
    INPUT='{}'
  fi
}

field() {
  echo "$INPUT" | jq -r ".$1 // empty" 2>/dev/null || echo ""
}

# ── Warning infrastructure ──────────────────────────────────────────
# Collect warnings during hook execution. These get surfaced to Claude
# via additionalContext so failures are visible, not silent.
hook_warn() {
  local msg="$1"
  _HOOK_WARNINGS+=("$msg")
  echo "[obsidian-memory] WARNING: $msg" >&2
}

# Output collected warnings as hook JSON. Call at end of sync hooks.
# Returns non-empty JSON if there are warnings, empty string if clean.
emit_warnings() {
  if [ ${#_HOOK_WARNINGS[@]} -eq 0 ]; then
    return
  fi
  local joined=""
  for w in "${_HOOK_WARNINGS[@]}"; do
    [ -n "$joined" ] && joined="$joined; "
    joined="$joined$w"
  done
  jq -n --arg ctx "[OM] $joined" '{
    hookSpecificOutput: {
      hookEventName: "ObsidianMemory",
      additionalContext: $ctx
    }
  }'
}

# ── Version check (once per session, non-blocking) ──────────────────
check_hook_version() {
  # Only check once per session (file acts as debounce)
  if [ -f "$_VERSION_CHECK_FILE" ]; then
    local last_check
    last_check=$(cat "$_VERSION_CHECK_FILE" 2>/dev/null || echo "0")
    local now
    now=$(date +%s)
    # Check at most once per hour
    if [ $((now - last_check)) -lt 3600 ]; then
      return
    fi
  fi
  date +%s > "$_VERSION_CHECK_FILE" 2>/dev/null || true

  # Fetch latest version from GitHub (non-blocking, 2s timeout)
  local remote_version
  remote_version=$(curl -sf --connect-timeout 2 --max-time 2 \
    "https://raw.githubusercontent.com/jodfie/Obsidian-Memory/main/.claude/hooks/_lib.sh" 2>/dev/null \
    | grep -m1 '^OM_HOOKS_VERSION=' | cut -d'"' -f2) || return 0

  if [ -n "$remote_version" ] && [ "$remote_version" != "$OM_HOOKS_VERSION" ]; then
    hook_warn "OM hooks outdated (local: v${OM_HOOKS_VERSION}, remote: v${remote_version}). Update: OM_HOST=\$OM_HOST bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/jodfie/Obsidian-Memory/main/scripts/setup-remote-om.sh)\""
  fi
}

# ── Session guard ───────────────────────────────────────────────────
# Use require_session for hooks that need a session but should not
# block if one doesn't exist. Warns instead of silently exiting.
require_session() {
  if [ -z "$SESSION_ID" ]; then
    hook_warn "No OM session active. Session tracking is disabled for this hook."
    emit_warnings
    exit 0
  fi
}

# ── API helpers ─────────────────────────────────────────────────────
# Returns response body. Sets _API_HTTP_CODE to HTTP status.
_API_HTTP_CODE=""

api_get() {
  local response
  _API_HTTP_CODE=""
  response=$(curl -s --connect-timeout 2 --max-time 5 \
    -w "\n%{http_code}" \
    -H "Content-Type: application/json" \
    "${API_URL}/$1" 2>/dev/null) || { echo ""; return 1; }
  _API_HTTP_CODE=$(echo "$response" | tail -1)
  echo "$response" | sed '$d'
}

api_post() {
  local endpoint="$1"
  local data="$2"
  local response
  _API_HTTP_CODE=""
  response=$(curl -s --connect-timeout 2 --max-time 5 \
    -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$data" \
    "${API_URL}/${endpoint}" 2>/dev/null) || { echo ""; return 1; }
  _API_HTTP_CODE=$(echo "$response" | tail -1)
  echo "$response" | sed '$d'
}

is_backend_up() {
  curl -sf --connect-timeout 2 --max-time 3 \
    "${API_URL}/health" >/dev/null 2>&1
}

# ── Session validation ──────────────────────────────────────────────
# Checks if the current SESSION_ID is still valid on the backend.
# Returns 0 if valid, 1 if not (404, unreachable, etc).
validate_session() {
  if [ -z "$SESSION_ID" ]; then
    return 1
  fi
  local body
  body=$(api_get "api/sessions/${SESSION_ID}")
  if [ "$_API_HTTP_CODE" = "200" ] && [ -n "$body" ]; then
    return 0
  fi
  return 1
}

# Re-creates a session on the backend if the current one is stale.
# Updates SESSION_ID, session file, and env file.
recreate_session() {
  local project="${1:-}"
  local claude_session_id="${2:-$SESSION_ID}"

  local response
  response=$(api_post "api/sessions" "{
    \"session_id\": \"${claude_session_id}\",
    \"project\": \"${project}\"
  }")

  local new_id
  new_id=$(echo "$response" | jq -r '.session_id // empty' 2>/dev/null || echo "")
  if [ -z "$new_id" ]; then
    hook_warn "Failed to create OM session (API returned: ${_API_HTTP_CODE})"
    return 1
  fi

  SESSION_ID="$new_id"

  # Update session file
  jq -n \
    --arg sid "$new_id" \
    --arg csid "$claude_session_id" \
    --arg url "$API_URL" \
    --arg proj "$project" \
    '{session_id: $sid, claude_session_id: $csid, api_url: $url, project: $proj}' \
    > "$SESSION_FILE"

  # Update env file if available
  if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export OBSIDIAN_MEMORY_SESSION_ID=\"${new_id}\"" >> "$CLAUDE_ENV_FILE"
    echo "export OBSIDIAN_MEMORY_API_URL=\"${API_URL}\"" >> "$CLAUDE_ENV_FILE"
    echo "export OBSIDIAN_MEMORY_PROJECT=\"${project}\"" >> "$CLAUDE_ENV_FILE"
  fi

  return 0
}

# ── Observe helper ──────────────────────────────────────────────────
# Usage: observe_event "event_type" "content" '{"key": "value"}'
observe_event() {
  local event_type="$1"
  local content="$2"
  local metadata="${3:-\{\}}"

  local escaped_content
  escaped_content=$(echo "$content" | jq -Rs '.' 2>/dev/null || echo "\"$content\"")

  local result
  result=$(api_post "api/sessions/observe" "{
    \"session_id\": \"${SESSION_ID}\",
    \"event_type\": \"${event_type}\",
    \"content\": ${escaped_content},
    \"metadata\": ${metadata}
  }")

  # Warn on failure but don't block the hook
  if [ "$_API_HTTP_CODE" != "200" ] && [ "$_API_HTTP_CODE" != "201" ]; then
    if [ "$_API_HTTP_CODE" = "404" ]; then
      hook_warn "Session ${SESSION_ID} not found on backend (observation lost). Session may need re-creation."
    elif [ -z "$_API_HTTP_CODE" ]; then
      hook_warn "OM API unreachable at ${API_URL} (observation lost)"
    else
      hook_warn "Observation failed with HTTP ${_API_HTTP_CODE}"
    fi
  fi
}
