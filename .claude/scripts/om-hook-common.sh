#!/usr/bin/env bash
# om-hook-common.sh — Shared OM integration for non-Claude-Code AI tools
# Source this from Cline, Copilot CLI, Cursor, Windsurf hook scripts.
#
# Usage: source om-hook-common.sh
# Provides: om_session_ensure, om_observe, om_end_session

set -euo pipefail

OM_API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
_OM_SESSION_ID=""
_OM_SOURCE=""          # set by caller: "cline", "copilot", "cursor", "windsurf"
_OM_SESSION_FILE=""    # set by caller: unique per tool

# Load session from file if it exists
_om_load_session() {
  if [ -f "$_OM_SESSION_FILE" ]; then
    _OM_SESSION_ID=$(jq -r '.session_id // empty' "$_OM_SESSION_FILE" 2>/dev/null || echo "")
    local saved_url
    saved_url=$(jq -r '.api_url // empty' "$_OM_SESSION_FILE" 2>/dev/null || echo "")
    [ -n "$saved_url" ] && OM_API_URL="$saved_url"
  fi
}

# Ensure an OM session exists for this tool session.
# Args: $1=tool_session_id $2=project_name
om_session_ensure() {
  local tool_session_id="${1:-unknown}"
  local project="${2:-}"

  _om_load_session

  # If we have a session, validate it
  if [ -n "$_OM_SESSION_ID" ]; then
    local saved_tool_sid
    saved_tool_sid=$(jq -r '.tool_session_id // empty' "$_OM_SESSION_FILE" 2>/dev/null || echo "")
    if [ "$saved_tool_sid" = "$tool_session_id" ]; then
      # Same tool session — check backend
      local code
      code=$(curl -sf --connect-timeout 2 --max-time 3 -o /dev/null -w "%{http_code}" \
        "${OM_API_URL}/api/sessions/${_OM_SESSION_ID}" 2>/dev/null || echo "000")
      [ "$code" = "200" ] && return 0
    fi
    # Stale or different session — recreate
    rm -f "$_OM_SESSION_FILE"
    _OM_SESSION_ID=""
  fi

  # Create new session
  local response
  response=$(curl -sf --connect-timeout 2 --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d "{\"session_id\": \"${_OM_SOURCE}-${tool_session_id}\", \"project\": \"${project}\"}" \
    "${OM_API_URL}/api/sessions" 2>/dev/null || echo "")

  _OM_SESSION_ID=$(echo "$response" | jq -r '.session_id // empty' 2>/dev/null || echo "")
  if [ -z "$_OM_SESSION_ID" ]; then
    echo "[om-${_OM_SOURCE}] WARNING: Failed to create OM session" >&2
    return 1
  fi

  jq -n \
    --arg sid "$_OM_SESSION_ID" \
    --arg tsid "$tool_session_id" \
    --arg url "$OM_API_URL" \
    --arg proj "$project" \
    --arg src "$_OM_SOURCE" \
    '{session_id: $sid, tool_session_id: $tsid, api_url: $url, project: $proj, source: $src}' \
    > "$_OM_SESSION_FILE"

  return 0
}

# Send an observation to OM.
# Args: $1=event_type $2=content $3=metadata_json (optional)
om_observe() {
  [ -z "$_OM_SESSION_ID" ] && return 0

  local event_type="$1"
  local content="$2"
  local metadata="${3:-{}}"

  # Truncate content to prevent oversized payloads
  if [ ${#content} -gt 1000 ]; then
    content="${content:0:1000}..."
  fi

  local escaped_content
  escaped_content=$(echo "$content" | jq -Rs '.' 2>/dev/null || echo "\"$content\"")

  curl -sf --connect-timeout 2 --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d "{\"session_id\": \"${_OM_SESSION_ID}\", \"event_type\": \"${event_type}\", \"content\": ${escaped_content}, \"metadata\": ${metadata}}" \
    "${OM_API_URL}/api/sessions/observe" >/dev/null 2>&1 || true
}

# End the OM session and clean up.
om_end_session() {
  [ -z "$_OM_SESSION_ID" ] && return 0

  curl -sf --connect-timeout 2 --max-time 5 \
    -X POST -H "Content-Type: application/json" \
    -d '{"auto_summarize": true}' \
    "${OM_API_URL}/api/sessions/${_OM_SESSION_ID}/end" >/dev/null 2>&1 || true

  rm -f "$_OM_SESSION_FILE" 2>/dev/null || true
  _OM_SESSION_ID=""
}

# Request a session summary from OM.
om_summarize() {
  [ -z "$_OM_SESSION_ID" ] && return 0

  curl -sf --connect-timeout 2 --max-time 25 \
    -X POST -H "Content-Type: application/json" \
    -d '{"force_incremental": true}' \
    "${OM_API_URL}/api/sessions/${_OM_SESSION_ID}/summary" >/dev/null 2>&1 || true
}
