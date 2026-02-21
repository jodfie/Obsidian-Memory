#!/usr/bin/env bash
# Obsidian-Memory REST API helper functions for OpenClaw agents
# Source this file in other scripts: source "$(dirname "$0")/_lib.sh"

set -euo pipefail

API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765/api}"
API_KEY="${OBSIDIAN_MEMORY_API_KEY:-}"

# --- HTTP helpers ---

_auth_header() {
    if [ -n "$API_KEY" ]; then
        echo "Authorization: Bearer $API_KEY"
    else
        echo "X-No-Auth: true"
    fi
}

mem_get() {
    local endpoint="$1"
    curl -sf \
        -H "$(_auth_header)" \
        -H "Accept: application/json" \
        "${API_URL}/${endpoint}"
}

mem_post() {
    local endpoint="$1"
    local data="$2"
    curl -sf \
        -X POST \
        -H "$(_auth_header)" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d "$data" \
        "${API_URL}/${endpoint}"
}

mem_put() {
    local endpoint="$1"
    local data="$2"
    curl -sf \
        -X PUT \
        -H "$(_auth_header)" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d "$data" \
        "${API_URL}/${endpoint}"
}

mem_delete_req() {
    local endpoint="$1"
    curl -sf \
        -X DELETE \
        -H "$(_auth_header)" \
        -H "Accept: application/json" \
        "${API_URL}/${endpoint}"
}

# --- High-level helpers ---

# Search notes
mem_search() {
    local query="$1"
    local limit="${2:-10}"
    mem_post "notes/search" "$(jq -n --arg q "$query" --argjson l "$limit" '{query: $q, limit: $l}')"
}

# Read a note by ID
mem_read_note() {
    local note_id="$1"
    mem_get "notes/${note_id}"
}

# Write/create a note
mem_write_note() {
    local title="$1"
    local content="$2"
    local rel_path="$3"
    local note_type="${4:-note}"
    local project="${5:-}"
    local tags_csv="${6:-}"

    local payload
    payload=$(jq -n \
        --arg t "$title" \
        --arg c "$content" \
        --arg p "$rel_path" \
        --arg nt "$note_type" \
        '{title: $t, content: $c, relative_path: $p, note_type: $nt}')

    if [ -n "$project" ]; then
        payload=$(echo "$payload" | jq --arg proj "$project" '. + {project: $proj}')
    fi
    if [ -n "$tags_csv" ]; then
        payload=$(echo "$payload" | jq --arg tags "$tags_csv" '. + {tags: ($tags | split(","))}')
    fi

    mem_post "notes" "$payload"
}

# Log a session observation
mem_session_observe() {
    local session_id="$1"
    local event_type="$2"
    local content="$3"
    mem_post "sessions/${session_id}/events" \
        "$(jq -n --arg et "$event_type" --arg c "$content" '{event_type: $et, content: $c}')"
}

# List projects
mem_list_projects() {
    mem_get "projects"
}

# Get project profile
mem_get_profile() {
    local project="$1"
    mem_get "profile/${project}"
}

# Check API health
mem_health() {
    mem_get "health"
}

# Check for errors in API response
check_error() {
    local response
    response=$(cat)
    if echo "$response" | jq -e '.error' >/dev/null 2>&1; then
        local error
        error=$(echo "$response" | jq -r '.error // "Unknown error"')
        echo "Error: $error" >&2
        return 1
    fi
    echo "$response"
    return 0
}
