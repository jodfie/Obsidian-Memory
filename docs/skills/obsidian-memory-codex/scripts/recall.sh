#!/usr/bin/env bash
# Quick recall — search notes and show profile summary
# Usage: ./recall.sh <query> [project]

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

QUERY="${1:?Usage: recall.sh <query> [project]}"
PROJECT="${2:-}"

echo "=== Memory Search: $QUERY ==="
echo ""

# Search for relevant notes
PAYLOAD=$(jq -n --arg q "$QUERY" --argjson l 5 '{query: $q, limit: $l}')
if [ -n "$PROJECT" ]; then
    PAYLOAD=$(echo "$PAYLOAD" | jq --arg p "$PROJECT" '. + {project: $p}')
fi

SEARCH=$(mem_post "notes/search" "$PAYLOAD" 2>/dev/null || echo '{"results":[]}')

echo "$SEARCH" | jq -r '
    if (.results | length) > 0 then
        "Found \(.results | length) relevant notes:\n",
        (.results[] | "  [\(.id)] \(.title // .permalink) (\(.note_type // "note"))\n       \(.snippet // (.content // "" | .[0:100]))\n")
    else
        "No matching notes found.\n"
    end
'

# Show profile if project specified
if [ -n "$PROJECT" ]; then
    echo "=== Project Profile: $PROJECT ==="
    echo ""
    PROFILE=$(mem_get "profile/${PROJECT}" 2>/dev/null || echo '{}')
    echo "$PROFILE" | jq -r '
        if .facts then
            "Facts:\n",
            (.facts[]? | "  - \(.)"),
            "\nPatterns:\n",
            (.patterns[]? | "  - \(.)")
        else
            "No profile data available."
        end
    '
fi
