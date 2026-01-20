#!/bin/bash
# Interactive script to set up Infisical credentials

set -euo pipefail

CREDS_FILE="$HOME/.infisical-machine-identity"

echo "=========================================="
echo "Infisical CLI Credentials Setup"
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

echo "Please provide your Infisical credentials:"
echo ""

# Get API URL
read -p "1. Infisical API URL (e.g., https://app.infisical.com/api): " INFISICAL_API_URL
if [[ -z "$INFISICAL_API_URL" ]]; then
    echo "Error: API URL is required"
    exit 1
fi

# Get Client ID
read -p "2. Machine Identity Client ID: " INFISICAL_CLIENT_ID
if [[ -z "$INFISICAL_CLIENT_ID" ]]; then
    echo "Error: Client ID is required"
    exit 1
fi

# Get Client Secret
read -p "3. Machine Identity Client Secret: " INFISICAL_CLIENT_SECRET
if [[ -z "$INFISICAL_CLIENT_SECRET" ]]; then
    echo "Error: Client Secret is required"
    exit 1
fi

# Get Project ID
read -p "4. Project ID: " INFISICAL_PROJECT_ID
if [[ -z "$INFISICAL_PROJECT_ID" ]]; then
    echo "Error: Project ID is required"
    exit 1
fi

# Get Environment
read -p "5. Environment (dev/staging/prod) [dev]: " INFISICAL_ENVIRONMENT
INFISICAL_ENVIRONMENT="${INFISICAL_ENVIRONMENT:-dev}"

# Get Secret Path
read -p "6. Secret Path [/]: " INFISICAL_SECRET_PATH
INFISICAL_SECRET_PATH="${INFISICAL_SECRET_PATH:-/}"

# Create credentials file
cat > "$CREDS_FILE" <<EOF
# Infisical Machine Identity Credentials
# Generated: $(date -Iseconds)

INFISICAL_API_URL="$INFISICAL_API_URL"
INFISICAL_CLIENT_ID="$INFISICAL_CLIENT_ID"
INFISICAL_CLIENT_SECRET="$INFISICAL_CLIENT_SECRET"
INFISICAL_PROJECT_ID="$INFISICAL_PROJECT_ID"
INFISICAL_ENVIRONMENT="$INFISICAL_ENVIRONMENT"
INFISICAL_SECRET_PATH="$INFISICAL_SECRET_PATH"
EOF

# Set permissions
chmod 600 "$CREDS_FILE"

echo ""
echo "✅ Credentials file created at: $CREDS_FILE"
echo ""

# Test configuration
echo "Testing Infisical CLI..."
if ~/.local/bin/infisical-cli secrets > /dev/null 2>&1; then
    echo "✅ Infisical CLI is working!"
    echo ""
    echo "You can now use:"
    echo "  infisical-cli secrets                    # List secrets"
    echo "  infisical-cli secrets get SECRET_NAME    # Get a secret"
    echo "  infisical-cli export --format=dotenv     # Export to .env"
else
    echo "⚠️  Infisical CLI test failed. Please verify your credentials."
    echo "   Check: ~/.infisical-machine-identity"
fi
