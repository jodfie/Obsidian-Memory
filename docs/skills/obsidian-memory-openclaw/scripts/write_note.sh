#!/usr/bin/env bash
# Create or update a note in Obsidian-Memory
# Usage: ./write_note.sh <title> <content> <relative_path> [note_type] [project] [tags]

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

TITLE="${1:?Usage: write_note.sh <title> <content> <relative_path> [note_type] [project] [tags]}"
CONTENT="${2:?Content is required}"
REL_PATH="${3:?Relative path is required}"
NOTE_TYPE="${4:-note}"
PROJECT="${5:-}"
TAGS="${6:-}"

RESPONSE=$(mem_write_note "$TITLE" "$CONTENT" "$REL_PATH" "$NOTE_TYPE" "$PROJECT" "$TAGS")

echo "$RESPONSE" | check_error | jq -r '
    if .id then
        "Note created/updated:\n  ID: \(.id)\n  Title: \(.title)\n  Path: \(.relative_path)\n  Type: \(.note_type // "note")"
    else
        .
    end
'
