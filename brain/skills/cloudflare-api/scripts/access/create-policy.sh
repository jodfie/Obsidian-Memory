#!/bin/bash
# Create Cloudflare Access policy

set -e
cd "$(dirname "$0")"
source "../_lib.sh"

# Parse arguments
DOMAIN=""
APP_ID=""
NAME=""
EMAIL=""
EMAIL_DOMAIN=""
DECISION="allow"

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --app-id)
            APP_ID="$2"
            shift 2
            ;;
        --name)
            NAME="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --email-domain)
            EMAIL_DOMAIN="$2"
            shift 2
            ;;
        --decision)
            DECISION="$2"
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

if [ -z "$DOMAIN" ] || [ -z "$APP_ID" ]; then
    echo "Usage: $0 <domain> --app-id <app-id> --name <policy-name> [--email <email>] [--email-domain <domain>] [--decision allow|deny]"
    echo "Example: $0 redleif.dev --app-id 123abc --name \"Allow Jody\" --email jody@example.com"
    echo "Example: $0 redleif.dev --app-id 123abc --name \"Allow Team\" --email-domain \"example.com\""
    exit 1
fi

# Default policy name
if [ -z "$NAME" ]; then
    NAME="Default Policy"
fi

# Get account ID
ACCOUNT_ID=$(get_account_id)
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Could not get account ID" >&2
    exit 1
fi

echo "🔑 Creating Access policy:"
echo "  App ID: $APP_ID"
echo "  Name: $NAME"
echo "  Decision: $DECISION"
[ -n "$EMAIL" ] && echo "  Email: $EMAIL"
[ -n "$EMAIL_DOMAIN" ] && echo "  Email Domain: $EMAIL_DOMAIN"

# Build include rules
INCLUDE_RULES=""
if [ -n "$EMAIL" ]; then
    INCLUDE_RULES="{
        \"email\": {
            \"email\": \"$EMAIL\"
        }
    }"
elif [ -n "$EMAIL_DOMAIN" ]; then
    INCLUDE_RULES="{
        \"email_domain\": {
            \"domain\": \"$EMAIL_DOMAIN\"
        }
    }"
else
    echo "❌ Must specify either --email or --email-domain"
    exit 1
fi

# Create policy data
POLICY_DATA=$(cat <<EOF
{
    "name": "$NAME",
    "decision": "$DECISION",
    "include": [
        $INCLUDE_RULES
    ],
    "precedence": 1
}
EOF
)

response=$(cf_post "/accounts/${ACCOUNT_ID}/access/apps/${APP_ID}/policies" "$POLICY_DATA")

if ! check_error "$response"; then
    exit 1
fi

POLICY_ID=$(echo "$response" | jq -r '.result.id')
echo "✅ Access policy created!"
echo "   Policy ID: $POLICY_ID"
echo ""
echo "🔐 Your application is now protected by Cloudflare Access!"