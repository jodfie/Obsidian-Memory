#!/bin/bash
# Create Cloudflare Access application

set -e
cd "$(dirname "$0")"
source "../_lib.sh"

# Parse arguments
DOMAIN=""
NAME=""
SUBDOMAIN=""
SERVICE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --name)
            NAME="$2"
            shift 2
            ;;
        --subdomain)
            SUBDOMAIN="$2"
            shift 2
            ;;
        --service)
            SERVICE="$2"
            shift 2
            ;;
        *)
            if [ -z "$DOMAIN" ]; then
                DOMAIN="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain> --name <app-name> [--subdomain <sub>] [--service <url>]"
    echo "Example: $0 redleif.dev --name \"Time Tracker\" --subdomain time --service http://localhost:3000"
    exit 1
fi

# Default values
if [ -z "$NAME" ]; then
    if [ -n "$SUBDOMAIN" ]; then
        NAME="$SUBDOMAIN.$DOMAIN"
    else
        NAME="$DOMAIN"
    fi
fi

if [ -z "$SUBDOMAIN" ]; then
    FULL_DOMAIN="$DOMAIN"
else
    FULL_DOMAIN="$SUBDOMAIN.$DOMAIN"
fi

# Get account ID
ACCOUNT_ID=$(get_account_id)
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Could not get account ID" >&2
    exit 1
fi

echo "🔐 Creating Access application:"
echo "  Name: $NAME"
echo "  Domain: $FULL_DOMAIN"
[ -n "$SERVICE" ] && echo "  Service: $SERVICE"

# Create the application
ACCESS_DATA=$(cat <<EOF
{
    "name": "$NAME",
    "domain": "$FULL_DOMAIN",
    "type": "self_hosted",
    "session_duration": "24h",
    "auto_redirect_to_identity": false,
    "enable_binding_cookie": true,
    "http_only_cookie_attribute": true,
    "same_site_cookie_attribute": "strict"
}
EOF
)

response=$(cf_post "/accounts/${ACCOUNT_ID}/access/apps" "$ACCESS_DATA")

if ! check_error "$response"; then
    exit 1
fi

APP_ID=$(echo "$response" | jq -r '.result.id')
echo "✅ Access application created!"
echo "   App ID: $APP_ID"
echo "   Domain: $FULL_DOMAIN"
echo ""
echo "🔑 Next steps:"
echo "1. Create an Access policy for this app:"
echo "   ./scripts/access/create-policy.sh $DOMAIN --app-id $APP_ID --name \"Allow Team\""
echo ""
echo "2. Configure your application to trust Cloudflare Access headers"