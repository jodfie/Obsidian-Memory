#!/bin/bash
# List Cloudflare Access applications

set -e
cd "$(dirname "$0")"
source "../_lib.sh"

# Get account ID
ACCOUNT_ID=$(get_account_id)
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Could not get account ID" >&2
    exit 1
fi

# Get format
FORMAT="table"
if [ "$1" = "--json" ]; then
    FORMAT="json"
fi

# List Access applications
response=$(cf_get "/accounts/${ACCOUNT_ID}/access/apps")

if ! check_error "$response"; then
    exit 1
fi

if [ "$FORMAT" = "json" ]; then
    echo "$response"
else
    echo "📱 Cloudflare Access Applications:"
    echo "$response" | jq -r '
        .result[] |
        "  • \(.name) - \(.domain) (\(.type))"
    '
fi