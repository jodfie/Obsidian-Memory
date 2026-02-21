#!/bin/bash
# Helper script to configure Cloudflare Access via Cloudflare Global API and Infisical

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Cloudflare Access Configuration"
echo "Using Cloudflare Global API + Infisical"
echo "=========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    exit 1
fi

# Check if infisical-cli is available
if ! command -v infisical-cli &> /dev/null; then
    echo "⚠️  Warning: infisical-cli not found"
    echo "   Cloudflare API configuration will still work, but Infisical integration will be skipped"
    echo ""
    USE_INFISICAL=false
else
    USE_INFISICAL=true

    # Check if credentials file exists
    if [[ ! -f "$HOME/.infisical-machine-identity" ]]; then
        echo "⚠️  Warning: Infisical credentials not found"
        echo "   Run ./scripts/setup-infisical.sh to set up Infisical"
        echo "   Continuing with Cloudflare API configuration only..."
        echo ""
        USE_INFISICAL=false
    else
        # Test Infisical connection
        echo "🔐 Testing Infisical connection..."
        if ! infisical-cli secrets > /dev/null 2>&1; then
            echo "⚠️  Warning: Cannot connect to Infisical"
            echo "   Continuing with Cloudflare API configuration only..."
            echo ""
            USE_INFISICAL=false
        else
            echo "✅ Infisical connected"
            echo ""
        fi
    fi
fi

# Step 1: Configure Cloudflare Access applications via API
echo "Step 1: Configuring Cloudflare Access Applications"
echo "---------------------------------------------------"
echo ""

# Check if Cloudflare credentials are in environment or Infisical
if [[ "$USE_INFISICAL" == "true" ]]; then
    # Try to get from Infisical first
    CLOUDFLARE_API_TOKEN=$(infisical-cli secrets get CLOUDFLARE_API_TOKEN --env=dev 2>/dev/null || echo "")
    CLOUDFLARE_ACCOUNT_ID=$(infisical-cli secrets get CLOUDFLARE_ACCOUNT_ID --env=dev 2>/dev/null || echo "")
fi

# Export to environment if found
if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    export CLOUDFLARE_API_TOKEN
fi
if [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
    export CLOUDFLARE_ACCOUNT_ID
fi

# Run Python configuration script
cd "$PROJECT_ROOT"
if ! python3 scripts/configure-cloudflare-access.py; then
    echo "❌ Error: Cloudflare API configuration failed"
    exit 1
fi

# Step 2: Store configuration in Infisical
if [[ "$USE_INFISICAL" == "true" ]]; then
    echo ""
    echo "Step 2: Storing configuration in Infisical"
    echo "---------------------------------------------------"
    echo ""

    # Get values from user or use defaults
    read -p "Enter Cloudflare Access team domain (e.g., your-team.cloudflareaccess.com): " TEAM_DOMAIN
    if [[ -z "$TEAM_DOMAIN" ]]; then
        echo "❌ Error: Team domain is required"
        exit 1
    fi

    # Get Cloudflare API credentials if not already set
    if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
        read -p "Enter Cloudflare API token (or leave empty to skip storing): " API_TOKEN
        if [[ -n "$API_TOKEN" ]]; then
            CLOUDFLARE_API_TOKEN="$API_TOKEN"
        fi
    fi

    if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
        read -p "Enter Cloudflare account ID (or leave empty to skip storing): " ACCOUNT_ID
        if [[ -n "$ACCOUNT_ID" ]]; then
            CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID"
        fi
    fi

    # Confirm environments
    echo ""
    echo "Which environments should be configured in Infisical?"
    read -p "Configure dev environment? (Y/n): " -n 1 -r
    echo
    CONFIGURE_DEV="${REPLY:-Y}"

    read -p "Configure prod environment? (Y/n): " -n 1 -r
    echo
    CONFIGURE_PROD="${REPLY:-Y}"

    # Configure dev environment
    if [[ $CONFIGURE_DEV =~ ^[Yy]$ ]]; then
        echo ""
        echo "📝 Storing dev environment secrets in Infisical..."
        infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true --env=dev
        infisical-cli secrets set CLOUDFLARE_ACCESS_TEAM_DOMAIN="$TEAM_DOMAIN" --env=dev
        
        if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
            infisical-cli secrets set CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" --env=dev
        fi
        if [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
            infisical-cli secrets set CLOUDFLARE_ACCOUNT_ID="$CLOUDFLARE_ACCOUNT_ID" --env=dev
        fi
        
        echo "✅ Dev environment configured in Infisical"
    fi

    # Configure prod environment
    if [[ $CONFIGURE_PROD =~ ^[Yy]$ ]]; then
        echo ""
        echo "📝 Storing prod environment secrets in Infisical..."
        infisical-cli secrets set CLOUDFLARE_ACCESS_ENABLED=true --env=prod
        infisical-cli secrets set CLOUDFLARE_ACCESS_TEAM_DOMAIN="$TEAM_DOMAIN" --env=prod
        
        if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
            infisical-cli secrets set CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" --env=prod
        fi
        if [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
            infisical-cli secrets set CLOUDFLARE_ACCOUNT_ID="$CLOUDFLARE_ACCOUNT_ID" --env=prod
        fi
        
        echo "✅ Prod environment configured in Infisical"
    fi

    # Ask about exporting to .env files
    echo ""
    read -p "Export secrets to .env files? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [[ $CONFIGURE_DEV =~ ^[Yy]$ ]]; then
            echo "📄 Exporting dev secrets to .env.dev..."
            infisical-cli export --format=dotenv --env=dev > .env.dev
            echo "✅ Exported to .env.dev"
        fi
        if [[ $CONFIGURE_PROD =~ ^[Yy]$ ]]; then
            echo "📄 Exporting prod secrets to .env.prod..."
            infisical-cli export --format=dotenv --env=prod > .env.prod
            echo "✅ Exported to .env.prod"
        fi
    fi
else
    echo ""
    echo "⚠️  Skipping Infisical storage (Infisical not available)"
    echo "   You can manually store these secrets later:"
    echo "   - CLOUDFLARE_ACCESS_ENABLED=true"
    echo "   - CLOUDFLARE_ACCESS_TEAM_DOMAIN=<your-team-domain>"
    echo "   - CLOUDFLARE_API_TOKEN=<your-api-token>"
    echo "   - CLOUDFLARE_ACCOUNT_ID=<your-account-id>"
fi

echo ""
echo "=========================================="
echo "✅ Cloudflare Access configuration complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✅ Cloudflare Access applications configured via API"
if [[ "$USE_INFISICAL" == "true" ]]; then
    echo "  ✅ Secrets stored in Infisical"
fi
echo ""
echo "Next steps:"
echo "1. Verify DNS is configured and proxied (orange cloud ☁️)"
echo "2. Deploy: make dev (or make prod)"
echo "3. Test authentication flow"
