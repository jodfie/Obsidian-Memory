#!/bin/bash
# Secure deployment script that fetches secrets from BWS at runtime
# Secrets are never stored in environment variables or shell history

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check for BWS
check_bws() {
    if ! command -v bws &> /dev/null; then
        if [ -f "$HOME/.local/bin/bws" ]; then
            BWS_CMD="$HOME/.local/bin/bws"
        else
            log_error "bws CLI not found. Please install Bitwarden Secrets Manager CLI."
            exit 1
        fi
    else
        BWS_CMD="bws"
    fi
}

# Load BWS credentials
load_bws_credentials() {
    if [ -f ~/.bitwarden-machine-identity ]; then
        source ~/.bitwarden-machine-identity
        export BWS_ACCESS_TOKEN
        export BWS_SERVER_URL
    else
        log_error "BWS credentials not found at ~/.bitwarden-machine-identity"
        exit 1
    fi
}

# Fetch a secret from BWS (output only, no env var)
get_secret() {
    local secret_id="$1"
    "$BWS_CMD" secret get "$secret_id" --output json 2>/dev/null | jq -r '.value'
}

# BWS Secret IDs for this project
CLOUDFLARE_OAUTH_CLIENT_ID_SECRET="bc173f8b-d8c8-4457-8451-b3d900519d3c"
CLOUDFLARE_OAUTH_CLIENT_SECRET_SECRET="0c56a162-4fcb-41bd-a63f-b3d90051a349"
CLOUDFLARE_ACCOUNT_ID_SECRET="51e5c353-0d52-4b0e-887c-b3d90047da22"
CLOUDFLARE_TUNNEL_TOKEN_SECRET="0a8db713-79ea-4c7e-b300-b3d9005b8d3e"

# Parse arguments
ENVIRONMENT="${1:-prod}"
ACTION="${2:-up}"

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Usage: $0 [dev|prod] [up|down|restart|logs]"
    exit 1
fi

log_info "Deploying Obsidian-Memory ($ENVIRONMENT environment)"

# Initialize BWS
check_bws
load_bws_credentials

log_info "Fetching secrets from BWS..."

# Create a temporary env file (will be deleted after use)
TEMP_ENV_FILE=$(mktemp)
trap "rm -f $TEMP_ENV_FILE" EXIT

# Fetch secrets and write to temp file (never in shell variables)
{
    echo "CLOUDFLARE_OAUTH_CLIENT_ID=$(get_secret $CLOUDFLARE_OAUTH_CLIENT_ID_SECRET)"
    echo "CLOUDFLARE_OAUTH_CLIENT_SECRET=$(get_secret $CLOUDFLARE_OAUTH_CLIENT_SECRET_SECRET)"
    echo "CLOUDFLARE_TUNNEL_TOKEN=$(get_secret $CLOUDFLARE_TUNNEL_TOKEN_SECRET)"
    echo "CLOUDFLARE_ACCESS_TEAM_DOMAIN=redleif.cloudflareaccess.com"
    echo "CLOUDFLARE_ACCESS_ENABLED=true"
} > "$TEMP_ENV_FILE"

# Set restrictive permissions
chmod 600 "$TEMP_ENV_FILE"

log_info "Secrets loaded securely"

# Determine compose files
COMPOSE_BASE="$PROJECT_DIR/docker-compose.yml"
if [ "$ENVIRONMENT" == "dev" ]; then
    COMPOSE_OVERRIDE="$PROJECT_DIR/docker-compose.dev.yml"
else
    COMPOSE_OVERRIDE="$PROJECT_DIR/docker-compose.prod.yml"
fi

# Build compose command
COMPOSE_CMD="docker compose -f $COMPOSE_BASE -f $COMPOSE_OVERRIDE --env-file $TEMP_ENV_FILE"

case "$ACTION" in
    up)
        log_info "Starting services..."
        $COMPOSE_CMD up -d --build
        log_info "Services started successfully"
        $COMPOSE_CMD ps
        ;;
    down)
        log_info "Stopping services..."
        $COMPOSE_CMD down
        log_info "Services stopped"
        ;;
    restart)
        log_info "Restarting services..."
        $COMPOSE_CMD down
        $COMPOSE_CMD up -d --build
        log_info "Services restarted"
        $COMPOSE_CMD ps
        ;;
    logs)
        $COMPOSE_CMD logs -f
        ;;
    ps)
        $COMPOSE_CMD ps
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Usage: $0 [dev|prod] [up|down|restart|logs|ps]"
        exit 1
        ;;
esac

log_info "Deployment complete"
