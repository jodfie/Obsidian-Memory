#!/bin/bash
# Bitwarden Personal CLI Session Helper
# Manages unlock sessions and provides convenient wrappers

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if logged in
check_login() {
    if ! bw status | grep -q "unauthenticated\|unlocked\|locked"; then
        echo -e "${RED}Bitwarden CLI not found or not configured${NC}"
        exit 1
    fi
    
    if bw status | grep -q "unauthenticated"; then
        echo -e "${RED}Not logged in. Run: bw login${NC}"
        exit 1
    fi
}

# Unlock vault and export session
unlock_vault() {
    check_login
    
    if bw status | grep -q "unlocked"; then
        echo -e "${GREEN}Vault already unlocked${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}Unlocking vault...${NC}"
    export BW_SESSION=$(bw unlock --raw)
    
    if [ -n "$BW_SESSION" ]; then
        echo -e "${GREEN}Vault unlocked. Session exported.${NC}"
        echo "Run: export BW_SESSION=\"$BW_SESSION\""
    else
        echo -e "${RED}Failed to unlock vault${NC}"
        exit 1
    fi
}

# Search for items by name or URL
search_item() {
    local query="$1"
    check_login
    
    if bw status | grep -q "locked"; then
        echo -e "${YELLOW}Vault locked. Unlocking...${NC}"
        unlock_vault
    fi
    
    echo -e "${YELLOW}Searching for: $query${NC}"
    bw list items --search "$query" | jq -r '.[] | "\(.id) | \(.name) | \(.login.username // "N/A")"'
}

# Get password by name/ID
get_password() {
    local identifier="$1"
    check_login
    
    if bw status | grep -q "locked"; then
        unlock_vault
    fi
    
    # Try as name first, then as ID
    if bw get password "$identifier" 2>/dev/null; then
        return 0
    elif bw get item "$identifier" 2>/dev/null | jq -r '.login.password // .notes // empty'; then
        return 0
    else
        echo -e "${RED}Item not found: $identifier${NC}"
        return 1
    fi
}

# Create simple login item
create_login() {
    local name="$1"
    local username="$2"
    local password="$3"
    local url="${4:-}"
    
    check_login
    
    if bw status | grep -q "locked"; then
        unlock_vault
    fi
    
    local item_json=$(cat <<EOF
{
  "type": 1,
  "name": "$name",
  "login": {
    "username": "$username",
    "password": "$password"
    $([ -n "$url" ] && echo ",\"uris\": [{\"match\": null, \"uri\": \"$url\"}]" || echo "")
  }
}
EOF
)
    
    echo "$item_json" | bw encode | bw create item
    echo -e "${GREEN}Created login item: $name${NC}"
}

# Create secure note
create_note() {
    local name="$1"
    local content="$2"
    
    check_login
    
    if bw status | grep -q "locked"; then
        unlock_vault
    fi
    
    local note_json=$(cat <<EOF
{
  "type": 2,
  "name": "$name",
  "secureNote": {
    "type": 0
  },
  "notes": "$content"
}
EOF
)
    
    echo "$note_json" | bw encode | bw create item
    echo -e "${GREEN}Created secure note: $name${NC}"
}

# Main command dispatcher
case "${1:-}" in
    "unlock"|"u")
        unlock_vault
        ;;
    "search"|"s")
        if [ -z "${2:-}" ]; then
            echo "Usage: $0 search <query>"
            exit 1
        fi
        search_item "$2"
        ;;
    "get"|"g")
        if [ -z "${2:-}" ]; then
            echo "Usage: $0 get <name-or-id>"
            exit 1
        fi
        get_password "$2"
        ;;
    "create-login"|"cl")
        if [ -z "${4:-}" ]; then
            echo "Usage: $0 create-login <name> <username> <password> [url]"
            exit 1
        fi
        create_login "$2" "$3" "$4" "${5:-}"
        ;;
    "create-note"|"cn")
        if [ -z "${3:-}" ]; then
            echo "Usage: $0 create-note <name> <content>"
            exit 1
        fi
        create_note "$2" "$3"
        ;;
    "status")
        bw status
        ;;
    "sync")
        bw sync
        echo -e "${GREEN}Sync complete${NC}"
        ;;
    *)
        echo "Usage: $0 {unlock|search|get|create-login|create-note|status|sync}"
        echo ""
        echo "Commands:"
        echo "  unlock (u)                     - Unlock vault and export session"
        echo "  search (s) <query>             - Search for items"
        echo "  get (g) <name-or-id>          - Get password/notes for item"
        echo "  create-login (cl) <args>       - Create login item"
        echo "  create-note (cn) <name> <content> - Create secure note"
        echo "  status                         - Show vault status"
        echo "  sync                           - Sync with server"
        exit 1
        ;;
esac