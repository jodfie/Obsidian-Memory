#!/bin/bash
# Interactive script to add secrets to Bitwarden Secrets Manager

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

echo "=========================================="
echo "Add Secret to Bitwarden Secrets Manager"
echo "=========================================="
echo ""

# Get secret key
read -p "Secret Key (e.g., DATABASE_URL): " SECRET_KEY
if [ -z "$SECRET_KEY" ]; then
    echo "Error: Secret key is required" >&2
    exit 1
fi

# Get secret value
read -sp "Secret Value: " SECRET_VALUE
echo ""
if [ -z "$SECRET_VALUE" ]; then
    echo "Error: Secret value is required" >&2
    exit 1
fi

# Get project ID (optional)
echo ""
read -p "Project ID (optional, press Enter to skip): " PROJECT_ID

# Get note (optional)
read -p "Note/Description (optional, press Enter to skip): " NOTE

# Create the secret
echo ""
echo "Creating secret..."

if [ -n "$PROJECT_ID" ]; then
    if [ -n "$NOTE" ]; then
        "$BWS_CMD" secret create \
            --key "$SECRET_KEY" \
            --value "$SECRET_VALUE" \
            --project-id "$PROJECT_ID" \
            --note "$NOTE"
    else
        "$BWS_CMD" secret create \
            --key "$SECRET_KEY" \
            --value "$SECRET_VALUE" \
            --project-id "$PROJECT_ID"
    fi
else
    if [ -n "$NOTE" ]; then
        "$BWS_CMD" secret create \
            --key "$SECRET_KEY" \
            --value "$SECRET_VALUE" \
            --note "$NOTE"
    else
        "$BWS_CMD" secret create \
            --key "$SECRET_KEY" \
            --value "$SECRET_VALUE"
    fi
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Secret '$SECRET_KEY' created successfully!"
else
    echo ""
    echo "❌ Failed to create secret" >&2
    exit 1
fi
