#!/usr/bin/env bash
# om.sh — Obsidian-Memory CLI helper for Claude Code hooks
# Primary interface for reading/writing notes. MCP tools are the fallback.
#
# Usage:
#   om.sh write --title "Title" --content "markdown" [--project P] [--type T] [--tags t1,t2] [--path rel/path.md]
#   om.sh read --id 123
#   om.sh read --permalink "slug"
#   om.sh read --query "search terms"
#   om.sh search "query" [--project P] [--tags t1,t2] [--type T] [--limit N]
#   om.sh update --id 123 --content "new content" [--title "new title"]
#   om.sh delete --id 123
#   om.sh supersede --old 123 --new 456 [--reason "why"]
#   om.sh projects
#   om.sh health

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────
API_URL="${OBSIDIAN_MEMORY_API_URL:-http://localhost:8765}"
SESSION_FILE="/tmp/obsidian-memory-session.json"

# Load API URL from session file if available
if [ -f "$SESSION_FILE" ]; then
  SAVED_URL=$(jq -r '.api_url // empty' "$SESSION_FILE" 2>/dev/null || echo "")
  [ -n "$SAVED_URL" ] && API_URL="$SAVED_URL"
fi

# ── Helpers ─────────────────────────────────────────────────────────
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

json_escape() {
  python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" 2>/dev/null
}

# ── Commands ────────────────────────────────────────────────────────

cmd_health() {
  if api GET "health" | jq -e '.status' >/dev/null 2>&1; then
    echo "OK — Obsidian-Memory API is up at ${API_URL}"
  else
    die "Cannot reach Obsidian-Memory API at ${API_URL}"
  fi
}

cmd_write() {
  local title="" content="" project="" note_type="note" tags="" rel_path=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title)    title="$2"; shift 2 ;;
      --content)  content="$2"; shift 2 ;;
      --project)  project="$2"; shift 2 ;;
      --type)     note_type="$2"; shift 2 ;;
      --tags)     tags="$2"; shift 2 ;;
      --path)     rel_path="$2"; shift 2 ;;
      --content-file) content=$(cat "$2"); shift 2 ;;
      *) die "Unknown write option: $1" ;;
    esac
  done

  [ -z "$title" ] && die "write requires --title"
  [ -z "$content" ] && die "write requires --content or --content-file"

  # Default relative path from project + title
  if [ -z "$rel_path" ]; then
    local slug
    slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g; s/--*/-/g; s/^-//; s/-$//')
    if [ -n "$project" ]; then
      rel_path="${project}/${slug}.md"
    else
      rel_path="${slug}.md"
    fi
  fi

  # Build tags array
  local tags_json="[]"
  if [ -n "$tags" ]; then
    tags_json=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
  fi

  # Build JSON payload with python for safe escaping
  local payload
  payload=$(python3 -c "
import json, sys
print(json.dumps({
    'title': sys.argv[1],
    'relative_path': sys.argv[2],
    'project': sys.argv[3] or None,
    'note_type': sys.argv[4],
    'tags': json.loads(sys.argv[5]),
    'content': sys.stdin.read()
}))
" "$title" "$rel_path" "$project" "$note_type" "$tags_json" <<< "$content")

  local response
  response=$(api POST "api/notes" -d "$payload") || {
    # Check if note was created by file watcher (race condition)
    # Search by relative path to verify
    local check
    check=$(api GET "api/notes?query=$(echo "$title" | head -c 50 | jq -sRr @uri)&limit=1")
    if echo "$check" | jq -e '.notes[0].id' >/dev/null 2>&1; then
      echo "$check" | jq '.notes[0]'
      return 0
    fi
    die "Failed to create note"
  }

  echo "$response" | jq '.'
}

cmd_read() {
  local id="" permalink="" query=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id)        id="$2"; shift 2 ;;
      --permalink) permalink="$2"; shift 2 ;;
      --query)     query="$2"; shift 2 ;;
      *) die "Unknown read option: $1" ;;
    esac
  done

  if [ -n "$id" ]; then
    api GET "api/notes/${id}" | jq '.'
  elif [ -n "$permalink" ]; then
    # Search by permalink
    local result
    result=$(api GET "api/notes?query=${permalink}&limit=5")
    echo "$result" | jq --arg p "$permalink" '.notes[] | select(.permalink == $p)' 2>/dev/null \
      || echo "$result" | jq '.notes[0]'
  elif [ -n "$query" ]; then
    local encoded
    encoded=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$query")
    api GET "api/notes?query=${encoded}&limit=1" | jq '.notes[0] // empty'
  else
    die "read requires --id, --permalink, or --query"
  fi
}

cmd_search() {
  local query="${1:-}"; shift || true
  local project="" tags="" note_type="" limit="20"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project) project="$2"; shift 2 ;;
      --tags)    tags="$2"; shift 2 ;;
      --type)    note_type="$2"; shift 2 ;;
      --limit)   limit="$2"; shift 2 ;;
      *) die "Unknown search option: $1" ;;
    esac
  done

  [ -z "$query" ] && die "search requires a query string"

  local encoded
  encoded=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$query")

  local url="api/notes?query=${encoded}&limit=${limit}"
  [ -n "$project" ] && url="${url}&project=${project}"
  [ -n "$note_type" ] && url="${url}&note_type=${note_type}"

  api GET "$url" | jq '{total: .total, notes: [.notes[] | {id, title, permalink, project, note_type, tags, updated_at}]}'
}

cmd_update() {
  local id="" title="" content=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id)      id="$2"; shift 2 ;;
      --title)   title="$2"; shift 2 ;;
      --content) content="$2"; shift 2 ;;
      --content-file) content=$(cat "$2"); shift 2 ;;
      *) die "Unknown update option: $1" ;;
    esac
  done

  [ -z "$id" ] && die "update requires --id"

  local payload
  payload=$(python3 -c "
import json, sys
data = {}
if sys.argv[1]: data['title'] = sys.argv[1]
if sys.argv[2]: data['content'] = sys.argv[2]
print(json.dumps(data))
" "$title" "$content")

  api PUT "api/notes/${id}" -d "$payload" | jq '.'
}

cmd_delete() {
  local id=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --id) id="$2"; shift 2 ;;
      *) die "Unknown delete option: $1" ;;
    esac
  done

  [ -z "$id" ] && die "delete requires --id"
  api DELETE "api/notes/${id}" | jq '.'
}

cmd_supersede() {
  local old="" new="" reason=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --old)    old="$2"; shift 2 ;;
      --new)    new="$2"; shift 2 ;;
      --reason) reason="$2"; shift 2 ;;
      *) die "Unknown supersede option: $1" ;;
    esac
  done

  [ -z "$old" ] && die "supersede requires --old"
  [ -z "$new" ] && die "supersede requires --new"

  local payload
  payload=$(python3 -c "
import json, sys
print(json.dumps({
    'old_note_id': int(sys.argv[1]),
    'new_note_id': int(sys.argv[2]),
    'reason': sys.argv[3] or None
}))
" "$old" "$new" "$reason")

  api POST "api/notes/supersede" -d "$payload" | jq '.'
}

cmd_projects() {
  api GET "api/projects" | jq '.projects'
}

# ── Dispatch ────────────────────────────────────────────────────────
COMMAND="${1:-help}"; shift || true

case "$COMMAND" in
  write)     cmd_write "$@" ;;
  read)      cmd_read "$@" ;;
  search)    cmd_search "$@" ;;
  update)    cmd_update "$@" ;;
  delete)    cmd_delete "$@" ;;
  supersede) cmd_supersede "$@" ;;
  projects)  cmd_projects ;;
  health)    cmd_health ;;
  help)
    echo "om.sh — Obsidian-Memory CLI for Claude Code"
    echo ""
    echo "Commands:"
    echo "  write    --title T --content C [--project P] [--type T] [--tags t1,t2] [--path p]"
    echo "  read     --id N | --permalink S | --query Q"
    echo "  search   QUERY [--project P] [--tags t1,t2] [--type T] [--limit N]"
    echo "  update   --id N [--title T] [--content C]"
    echo "  delete   --id N"
    echo "  supersede --old N --new N [--reason R]"
    echo "  projects"
    echo "  health"
    ;;
  *) die "Unknown command: $COMMAND. Run 'om.sh help' for usage." ;;
esac
