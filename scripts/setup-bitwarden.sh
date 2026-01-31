#!/bin/bash
# Interactive script to set up Bitwarden Secrets Manager credentials

set -euo pipefail

CREDS_FILE="$HOME/.bitwarden-machine-identity"

echo "=========================================="
echo "Bitwarden Secrets Manager Setup"
echo "=========================================="
echo ""

# Check if file already exists
if [[ -f "$CREDS_FILE" ]]; then
    echo "⚠️  Credentials file already exists at: $CREDS_FILE"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo "Please provide your Bitwarden Secrets Manager credentials:"
echo ""

# Get Access Token (Machine Identifier Key)
read -p "1. Machine Account Access Token (machine identifier key): " BWS_ACCESS_TOKEN
if [[ -z "$BWS_ACCESS_TOKEN" ]]; then
    echo "Error: Access Token is required"
    exit 1
fi

# Get Server URL (optional, defaults to cloud)
read -p "2. Bitwarden Server URL [https://vault.bitwarden.com]: " BWS_SERVER_URL
BWS_SERVER_URL="${BWS_SERVER_URL:-https://vault.bitwarden.com}"

# Get Project ID (optional)
read -p "3. Project ID (optional, leave empty if not using projects): " BWS_PROJECT_ID
BWS_PROJECT_ID="${BWS_PROJECT_ID:-}"

# Get Environment (optional, for organization)
read -p "4. Environment name (optional, e.g., dev/staging/prod): " BWS_ENVIRONMENT
BWS_ENVIRONMENT="${BWS_ENVIRONMENT:-}"

# Create credentials file
cat > "$CREDS_FILE" <<EOF
# Bitwarden Secrets Manager Machine Account Credentials
# Generated: $(date -Iseconds)
# 
# To use these credentials, source this file or set BWS_ACCESS_TOKEN in your environment

BWS_ACCESS_TOKEN="$BWS_ACCESS_TOKEN"
BWS_SERVER_URL="$BWS_SERVER_URL"
EOF

# Add optional fields if provided
if [[ -n "$BWS_PROJECT_ID" ]]; then
    echo "BWS_PROJECT_ID=\"$BWS_PROJECT_ID\"" >> "$CREDS_FILE"
fi

if [[ -n "$BWS_ENVIRONMENT" ]]; then
    echo "BWS_ENVIRONMENT=\"$BWS_ENVIRONMENT\"" >> "$CREDS_FILE"
fi

# Set permissions
chmod 600 "$CREDS_FILE"

echo ""
echo "✅ Credentials file created at: $CREDS_FILE"
echo ""

# Check if bws CLI is installed
if ! command -v bws &> /dev/null; then
    echo "⚠️  Bitwarden Secrets Manager CLI (bws) not found in PATH"
    echo ""
    echo "To install bws CLI:"
    echo "  1. Download from: https://github.com/bitwarden/sdk/releases"
    echo "  2. Extract and add to PATH"
    echo "  3. Or use: curl -L https://github.com/bitwarden/sdk/releases/latest/download/bws-linux -o /usr/local/bin/bws && chmod +x /usr/local/bin/bws"
    echo ""
    echo "After installing, you can test with:"
    echo "  source $CREDS_FILE && bws secret list"
else
    # Test configuration
    echo "Testing Bitwarden Secrets Manager CLI..."
    export BWS_ACCESS_TOKEN="$BWS_ACCESS_TOKEN"
    export BWS_SERVER_URL="$BWS_SERVER_URL"
    
    if bws secret list > /dev/null 2>&1; then
        echo "✅ Bitwarden Secrets Manager CLI is working!"
        echo ""
        echo "You can now use:"
        echo "  source $CREDS_FILE && bws secret list              # List secrets"
        echo "  source $CREDS_FILE && bws secret get SECRET_ID      # Get a secret"
        echo "  source $CREDS_FILE && bws run -- <command>          # Run command with secrets injected"
    else
        echo "⚠️  Bitwarden CLI test failed. Please verify your access token."
        echo "   Check: $CREDS_FILE"
        echo "   Make sure your access token has proper permissions"
    fi
fi

echo ""
echo "To use these credentials in your shell:"
echo "  source $CREDS_FILE"
echo ""
echo "Or add to your ~/.bashrc or ~/.zshrc:"
echo "  source $CREDS_FILE"
