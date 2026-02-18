#!/usr/bin/env bash
# Read a note from Obsidian-Memory by ID or search query
# Usage: ./read_note.sh <id_or_query>
#   If argument is a number, reads by ID
#   Otherwise, searches and returns first match

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

INPUT="${1:?Usage: read_note.sh <id_or_query>}"

if [[ "$INPUT" =~ ^[0-9]+$ ]]; then
    # Numeric — read by ID
    RESPONSE=$(mem_read_note "$INPUT")
else
    # Text — search and return first match
    SEARCH=$(mem_search "$INPUT" 1)
    NOTE_ID=$(echo "$SEARCH" | jq -r '.results[0].id // empty')
    if [ -z "$NOTE_ID" ]; then
        echo "No note found matching: $INPUT" >&2
        exit 1
    fi
    RESPONSE=$(mem_read_note "$NOTE_ID")
fi

echo "$RESPONSE" | check_error | jq -r '
    "# \(.title // "Untitled")\n",
    "ID: \(.id) | Type: \(.note_type // "note") | Project: \(.project // "none")",
    "Tags: \(.tags // [] | join(", "))",
    "Path: \(.relative_path // "unknown")",
    "Created: \(.created_at // "unknown") | Updated: \(.updated_at // "unknown")\n",
    "---\n",
    (.content // "No content")
'
