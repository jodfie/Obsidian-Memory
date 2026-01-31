#!/bin/bash
# List secrets from Bitwarden Secrets Manager

set -euo pipefail

# Load credentials
if [ -f ~/.bitwarden-machine-identity ]; then
    source ~/.bitwarden-machine-identity
    export BWS_ACCESS_TOKEN
    export BWS_SERVER_URL
fi

# Find bws
if command -v bws &> /dev/null; then
    BWS_CMD="bws"
elif [ -f "$HOME/.local/bin/bws" ]; then
    BWS_CMD="$HOME/.local/bin/bws"
else
    echo "Error: bws CLI not found" >&2
    exit 1
fi

PROJECT_ID="${1:-}"
OUTPUT_FORMAT="${2:-table}"

echo "=========================================="
echo "Bitwarden Secrets Manager - Secrets List"
echo "=========================================="
echo ""

if [ -n "$PROJECT_ID" ]; then
    echo "Project ID: $PROJECT_ID"
    echo ""
    "$BWS_CMD" secret list --project-id "$PROJECT_ID" --output "$OUTPUT_FORMAT"
else
    echo "All secrets (use --project-id to filter):"
    echo ""
    "$BWS_CMD" secret list --output "$OUTPUT_FORMAT"
fi
