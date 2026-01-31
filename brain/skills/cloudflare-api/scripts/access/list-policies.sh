#!/bin/bash
# List policies for a Cloudflare Access application

set -e
cd "$(dirname "$0")"
source "../_lib.sh"

# Parse arguments
APP_ID="$1"
FORMAT="table"

if [ "$2" = "--json" ] || [ "$1" = "--json" ]; then
    FORMAT="json"
fi

if [ -z "$APP_ID" ] && [ "$FORMAT" != "json" ]; then
    echo "Usage: $0 <app-id> [--json]"
    echo "Example: $0 abc123-def456-ghi789"
    echo ""
    echo "💡 Tip: Get app IDs with: ./list-apps.sh"
    exit 1
fi

# Get account ID
ACCOUNT_ID=$(get_account_id)
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Could not get account ID" >&2
    exit 1
fi

# List policies for the application
response=$(cf_get "/accounts/${ACCOUNT_ID}/access/apps/${APP_ID}/policies")

if ! check_error "$response"; then
    exit 1
fi

if [ "$FORMAT" = "json" ]; then
    echo "$response"
else
    echo "🔑 Access Policies for App: $APP_ID"
    echo "$response" | jq -r '
        .result[] |
        "  • \(.name) (\(.decision)) - Priority: \(.precedence)"
    '
fi