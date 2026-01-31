#!/bin/bash
# Helper script for retrieving secrets from Bitwarden Secrets Manager
# Usage: bitwarden-helper.sh get SECRET_ID
#        bitwarden-helper.sh list
#        bitwarden-helper.sh export

set -euo pipefail

CREDS_FILE="$HOME/.bitwarden-machine-identity"
# Try to find bws in common locations
if command -v bws &> /dev/null; then
    BWS_CMD="bws"
elif [[ -f "$HOME/.local/bin/bws" ]]; then
    BWS_CMD="$HOME/.local/bin/bws"
elif [[ -f "/usr/local/bin/bws" ]]; then
    BWS_CMD="/usr/local/bin/bws"
else
    BWS_CMD="bws"  # Will fail with better error message
fi

# Check if bws is installed
if ! command -v "$BWS_CMD" &> /dev/null; then
    echo "Error: Bitwarden Secrets Manager CLI (bws) not found" >&2
    echo "Install from: https://github.com/bitwarden/sdk/releases" >&2
    exit 1
fi

# Load credentials if file exists
if [[ -f "$CREDS_FILE" ]]; then
    # Source the credentials file
    set -a
    source "$CREDS_FILE"
    set +a
fi

# Check if access token is set
if [[ -z "${BWS_ACCESS_TOKEN:-}" ]]; then
    echo "Error: BWS_ACCESS_TOKEN not set" >&2
    echo "Set it in environment or create $CREDS_FILE" >&2
    exit 1
fi

# Export access token for bws
export BWS_ACCESS_TOKEN

# Set server URL if provided
if [[ -n "${BWS_SERVER_URL:-}" ]]; then
    export BWS_SERVER_URL
fi

# Function to get a secret
get_secret() {
    local secret_id="$1"
    if [[ -z "$secret_id" ]]; then
        echo "Error: Secret ID required" >&2
        echo "Usage: $0 get <secret-id>" >&2
        exit 1
    fi
    
    # Get secret value
    local result
    result=$("$BWS_CMD" secret get "$secret_id" --format json 2>&1)
    
    if [[ $? -ne 0 ]]; then
        echo "Error retrieving secret: $result" >&2
        exit 1
    fi
    
    # Extract value using jq if available, otherwise use grep/sed
    if command -v jq &> /dev/null; then
        echo "$result" | jq -r '.value // .'
    else
        # Fallback: try to extract value field
        echo "$result" | grep -o '"value":"[^"]*"' | sed 's/"value":"\(.*\)"/\1/'
    fi
}

# Function to list secrets
list_secrets() {
    "$BWS_CMD" secret list --format json 2>&1
}

# Function to export secrets as environment variables
export_secrets() {
    local format="${1:-dotenv}"
    
    if [[ "$format" == "dotenv" ]]; then
        # Export as .env format
        local secrets_json
        secrets_json=$("$BWS_CMD" secret list --format json 2>&1)
        
        if command -v jq &> /dev/null; then
            echo "$secrets_json" | jq -r '.[] | "\(.key)=\(.value)"'
        else
            echo "Error: jq is required for dotenv export" >&2
            echo "Install jq or use: $0 list" >&2
            exit 1
        fi
    else
        # Export as JSON
        "$BWS_CMD" secret list --format json 2>&1
    fi
}

# Main command handling
case "${1:-}" in
    get)
        get_secret "${2:-}"
        ;;
    list)
        list_secrets
        ;;
    export)
        export_secrets "${2:-dotenv}"
        ;;
    *)
        echo "Bitwarden Secrets Manager Helper" >&2
        echo "" >&2
        echo "Usage:" >&2
        echo "  $0 get <secret-id>     Get a specific secret value" >&2
        echo "  $0 list                List all secrets (JSON)" >&2
        echo "  $0 export [format]     Export secrets (dotenv or json)" >&2
        echo "" >&2
        echo "Examples:" >&2
        echo "  $0 get abc123def456     # Get secret by ID" >&2
        echo "  $0 list                 # List all secrets" >&2
        echo "  $0 export dotenv        # Export as .env format" >&2
        echo "  $0 export json          # Export as JSON" >&2
        exit 1
        ;;
esac
