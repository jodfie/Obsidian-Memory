#!/bin/bash
# Quick setup for Cloudflare Access protection

set -e
cd "$(dirname "$0")"

echo "🔐 Cloudflare Access Quick Setup"
echo "================================"
echo ""

# Parse arguments
DOMAIN="$1"
SUBDOMAIN="$2"
EMAIL="$3"

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain> [subdomain] [email]"
    echo "Example: $0 redleif.dev time jody@example.com"
    echo "Example: $0 redleif.dev \"\" jody@example.com  # for root domain"
    exit 1
fi

if [ -z "$EMAIL" ]; then
    read -p "Enter your email for access: " EMAIL
fi

# Determine full domain and app name
if [ -z "$SUBDOMAIN" ] || [ "$SUBDOMAIN" = "\"\"" ]; then
    FULL_DOMAIN="$DOMAIN"
    APP_NAME="$DOMAIN"
    SUBDOMAIN_FLAG=""
else
    FULL_DOMAIN="$SUBDOMAIN.$DOMAIN"
    APP_NAME="$SUBDOMAIN ($DOMAIN)"
    SUBDOMAIN_FLAG="--subdomain $SUBDOMAIN"
fi

echo "Setting up Access protection for: $FULL_DOMAIN"
echo ""

# Step 1: Create Access application
echo "1️⃣  Creating Access application..."
APP_RESPONSE=$(./create-app.sh "$DOMAIN" --name "$APP_NAME" $SUBDOMAIN_FLAG --service "http://localhost:3000")
APP_ID=$(echo "$APP_RESPONSE" | grep "App ID:" | cut -d: -f2 | xargs)

if [ -z "$APP_ID" ]; then
    echo "❌ Failed to create application"
    exit 1
fi

echo "✅ Application created: $APP_ID"
echo ""

# Step 2: Create Access policy
echo "2️⃣  Creating Access policy..."
./create-policy.sh "$DOMAIN" --app-id "$APP_ID" --name "Allow $EMAIL" --email "$EMAIL"
echo ""

echo "🎉 Success! Access protection is now active for $FULL_DOMAIN"
echo ""
echo "📝 Next steps:"
echo "   • Visit https://$FULL_DOMAIN - you should be prompted to authenticate"
echo "   • Configure your app to trust Cloudflare Access headers (CF-Access-Authenticated-User-Email)"
echo "   • Add more users/policies as needed via the Cloudflare dashboard"
echo ""
echo "🔗 Cloudflare Access Dashboard:"
echo "   https://dash.cloudflare.com/$(../../../scripts/setup.sh | grep Account | cut -d: -f2 | xargs)/access/apps"