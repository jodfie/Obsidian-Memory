#!/usr/bin/env bash
# _lib.sh — Shared functions for Obsidian-Memory Claude Code hooks
# Source this file at the top of each hook: source "$(dirname "$0")/_lib.sh"

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
SESSION_ID="${OBSIDIAN_MEMORY_SESSION_ID:-}"

# ── Input parsing ───────────────────────────────────────────────────
INPUT=""
read_input() {
  INPUT=$(cat 2>/dev/null || echo '{}')
  # Validate it's JSON; if not, reset to empty object
  if ! echo "$INPUT" | jq empty 2>/dev/null; then
    INPUT='{}'
  fi
}

# Extract a field from INPUT. Returns empty string on missing/null.
field() {
  echo "$INPUT" | jq -r ".$1 // empty" 2>/dev/null || echo ""
}

# ── Session guard ───────────────────────────────────────────────────
require_session() {
  if [ -z "$SESSION_ID" ]; then
    exit 0
  fi
}

# ── API helpers ─────────────────────────────────────────────────────
api_get() {
  curl -sf --connect-timeout 2 --max-time 5 \
    -H "Content-Type: application/json" \
    "${API_URL}/$1" 2>/dev/null || echo ""
}

api_post() {
  local endpoint="$1"
  local data="$2"
  curl -sf --connect-timeout 2 --max-time 5 \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$data" \
    "${API_URL}/${endpoint}" 2>/dev/null || echo ""
}

is_backend_up() {
  curl -sf --connect-timeout 2 --max-time 3 \
    "${API_URL}/health" >/dev/null 2>&1
}

# ── Observe helper ──────────────────────────────────────────────────
# Usage: observe_event "event_type" "content" '{"key": "value"}'
observe_event() {
  local event_type="$1"
  local content="$2"
  local metadata="${3:-\{\}}"

  # Escape content for JSON (handle quotes and newlines)
  local escaped_content
  escaped_content=$(echo "$content" | jq -Rs '.' 2>/dev/null || echo "\"$content\"")

  api_post "api/sessions/observe" "{
    \"session_id\": \"${SESSION_ID}\",
    \"event_type\": \"${event_type}\",
    \"content\": ${escaped_content},
    \"metadata\": ${metadata}
  }" >/dev/null 2>&1 || true
}
