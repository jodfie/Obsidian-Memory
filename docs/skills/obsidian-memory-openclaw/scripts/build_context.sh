#!/usr/bin/env bash
# Build context from memory:// URI patterns
# Usage: ./build_context.sh <uri1> [uri2] [uri3] ...
#
# Supported URI patterns:
#   memory://note/123          — Note by ID
#   memory://search/query      — Search for "query"
#   memory://tags/tag1,tag2    — Notes with tags
#   memory://project/name      — Notes in project
#   memory://path/rel/path     — Note by relative path

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

if [ $# -eq 0 ]; then
    echo "Usage: build_context.sh <uri1> [uri2] [uri3] ..."
    echo ""
    echo "URI patterns:"
    echo "  memory://note/123        — Note by ID"
    echo "  memory://search/query    — Search for 'query'"
    echo "  memory://tags/tag1,tag2  — Notes with tags"
    echo "  memory://project/name    — Notes in project"
    exit 1
fi

echo "=== Building Context ==="
echo ""

for URI in "$@"; do
    echo "--- $URI ---"

    # Parse URI
    SCHEME="${URI%%://*}"
    PATH_PART="${URI#*://}"
    TYPE="${PATH_PART%%/*}"
    VALUE="${PATH_PART#*/}"

    case "$TYPE" in
        note)
            # Read by ID
            RESPONSE=$(mem_read_note "$VALUE" 2>/dev/null || echo '{"error":"not found"}')
            echo "$RESPONSE" | jq -r '
                if .title then
                    "# \(.title)\n\(.content // "")\n"
                else
                    "Note \($ENV.VALUE // "unknown") not found.\n"
                end
            '
            ;;
        search)
            # Search
            RESPONSE=$(mem_search "$VALUE" 5 2>/dev/null || echo '{"results":[]}')
            echo "$RESPONSE" | jq -r '
                (.results[]? | "## \(.title // .permalink)\n\(.snippet // (.content // "" | .[0:200]))\n")
            '
            ;;
        tags)
            # Search by tags
            IFS=',' read -ra TAG_ARRAY <<< "$VALUE"
            PAYLOAD=$(jq -n --arg q "*" --argjson l 10 '{query: $q, limit: $l}')
            for tag in "${TAG_ARRAY[@]}"; do
                PAYLOAD=$(echo "$PAYLOAD" | jq --arg t "$tag" '.tags += [$t]')
            done
            RESPONSE=$(mem_post "notes/search" "$PAYLOAD" 2>/dev/null || echo '{"results":[]}')
            echo "$RESPONSE" | jq -r '
                (.results[]? | "## \(.title // .permalink)\n\(.snippet // (.content // "" | .[0:200]))\n")
            '
            ;;
        project)
            # Search by project
            PAYLOAD=$(jq -n --arg q "*" --arg p "$VALUE" --argjson l 10 '{query: $q, project: $p, limit: $l}')
            RESPONSE=$(mem_post "notes/search" "$PAYLOAD" 2>/dev/null || echo '{"results":[]}')
            echo "$RESPONSE" | jq -r '
                (.results[]? | "## \(.title // .permalink)\n\(.snippet // (.content // "" | .[0:200]))\n")
            '
            ;;
        *)
            echo "Unknown URI type: $TYPE"
            ;;
    esac
done

echo "=== Context Complete ==="
