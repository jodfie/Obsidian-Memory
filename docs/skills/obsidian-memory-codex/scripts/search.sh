#!/usr/bin/env bash
# Search Obsidian-Memory notes
# Usage: ./search.sh <query> [limit] [project] [note_type]

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

QUERY="${1:?Usage: search.sh <query> [limit] [project] [note_type]}"
LIMIT="${2:-10}"
PROJECT="${3:-}"
NOTE_TYPE="${4:-}"

# Build search payload
PAYLOAD=$(jq -n --arg q "$QUERY" --argjson l "$LIMIT" '{query: $q, limit: $l}')

if [ -n "$PROJECT" ]; then
    PAYLOAD=$(echo "$PAYLOAD" | jq --arg p "$PROJECT" '. + {project: $p}')
fi
if [ -n "$NOTE_TYPE" ]; then
    PAYLOAD=$(echo "$PAYLOAD" | jq --arg nt "$NOTE_TYPE" '. + {note_type: $nt}')
fi

RESPONSE=$(mem_post "notes/search" "$PAYLOAD")

# Format output
echo "$RESPONSE" | jq -r '
    if .results then
        "Found \(.total_count // (.results | length)) results:\n",
        (.results[] | "[\(.id)] \(.title // .permalink)\n    Type: \(.note_type // "note") | Tags: \(.tags // [] | join(", "))\n    \(.snippet // (.content // "" | .[0:120]))\n")
    else
        "No results found."
    end
'
