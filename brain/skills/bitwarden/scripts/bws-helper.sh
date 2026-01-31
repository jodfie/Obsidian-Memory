#!/bin/bash
# Bitwarden Secrets Manager CLI Helper
# Simplifies common bws operations and provides project management

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if BWS is available and token is set
check_setup() {
    if ! command -v bws &> /dev/null; then
        echo -e "${RED}bws command not found. Install with: npm install -g @bitwarden/sdk${NC}"
        exit 1
    fi
    
    if [ -z "${BWS_ACCESS_TOKEN:-}" ]; then
        echo -e "${RED}BWS_ACCESS_TOKEN not set${NC}"
        echo -e "${YELLOW}Set token with: export BWS_ACCESS_TOKEN=\"your-token\"${NC}"
        exit 1
    fi
}

# List all projects
list_projects() {
    check_setup
    echo -e "${BLUE}Available Projects:${NC}"
    bws project list | jq -r '.[] | "\(.id) | \(.name)"'
}

# Get project ID by name
get_project_id() {
    local project_name="$1"
    check_setup
    bws project list | jq -r ".[] | select(.name == \"$project_name\") | .id"
}

# List secrets in a project
list_secrets() {
    local project_identifier="$1"
    check_setup
    
    # Check if it's a UUID (project ID) or name
    if [[ "$project_identifier" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
        project_id="$project_identifier"
    else
        project_id=$(get_project_id "$project_identifier")
        if [ -z "$project_id" ]; then
            echo -e "${RED}Project not found: $project_identifier${NC}"
            exit 1
        fi
    fi
    
    echo -e "${BLUE}Secrets in project:${NC}"
    bws secret list --project-id "$project_id" | jq -r '.[] | "\(.id) | \(.key) | \(.note // "")"'
}

# Get secret value by name
get_secret() {
    local secret_name="$1"
    local project_identifier="${2:-}"
    check_setup
    
    if [ -n "$project_identifier" ]; then
        # Get project ID if name provided
        if [[ ! "$project_identifier" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
            project_identifier=$(get_project_id "$project_identifier")
        fi
        secrets=$(bws secret list --project-id "$project_identifier")
    else
        # Search all accessible projects
        projects=$(bws project list | jq -r '.[].id')
        secrets=""
        for proj in $projects; do
            proj_secrets=$(bws secret list --project-id "$proj" 2>/dev/null || echo "[]")
            if [ "$secrets" = "" ]; then
                secrets="$proj_secrets"
            else
                secrets=$(echo "$secrets $proj_secrets" | jq -s 'add')
            fi
        done
    fi
    
    secret_id=$(echo "$secrets" | jq -r ".[] | select(.key == \"$secret_name\") | .id")
    
    if [ -z "$secret_id" ]; then
        echo -e "${RED}Secret not found: $secret_name${NC}"
        exit 1
    fi
    
    bws secret get "$secret_id" | jq -r '.value'
}

# Create a new secret
create_secret() {
    local key="$1"
    local value="$2"
    local project_identifier="$3"
    local note="${4:-}"
    
    check_setup
    
    # Get project ID if name provided
    if [[ ! "$project_identifier" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
        project_id=$(get_project_id "$project_identifier")
        if [ -z "$project_id" ]; then
            echo -e "${RED}Project not found: $project_identifier${NC}"
            exit 1
        fi
    else
        project_id="$project_identifier"
    fi
    
    if [ -n "$note" ]; then
        bws secret create "$key" "$value" --project-id "$project_id" --note "$note"
    else
        bws secret create "$key" "$value" --project-id "$project_id"
    fi
    
    echo -e "${GREEN}Created secret: $key${NC}"
}

# Run command with secrets injected
run_with_secrets() {
    local project_identifier="${1:-}"
    shift
    local command="$*"
    
    check_setup
    
    if [ -n "$project_identifier" ]; then
        # Get project ID if name provided
        if [[ ! "$project_identifier" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
            project_id=$(get_project_id "$project_identifier")
            if [ -z "$project_id" ]; then
                echo -e "${RED}Project not found: $project_identifier${NC}"
                exit 1
            fi
        else
            project_id="$project_identifier"
        fi
        
        echo -e "${YELLOW}Running with secrets from project: $project_identifier${NC}"
        bws run --project-id "$project_id" -- "$command"
    else
        echo -e "${YELLOW}Running with all accessible secrets${NC}"
        bws run -- "$command"
    fi
}

# Import from personal vault to secrets manager
import_from_bw() {
    local bw_item_name="$1"
    local secret_key="$2"
    local project_identifier="$3"
    
    echo -e "${YELLOW}Importing from personal vault...${NC}"
    
    # Get from personal vault
    if ! command -v bw &> /dev/null; then
        echo -e "${RED}bw command not found for import${NC}"
        exit 1
    fi
    
    # Try to get the value from personal vault
    if secret_value=$(bw get password "$bw_item_name" 2>/dev/null); then
        echo -e "${GREEN}Found password for $bw_item_name${NC}"
    elif secret_value=$(bw get notes "$bw_item_name" 2>/dev/null); then
        echo -e "${GREEN}Found notes for $bw_item_name${NC}"
    else
        echo -e "${RED}Could not find $bw_item_name in personal vault${NC}"
        exit 1
    fi
    
    # Create in secrets manager
    create_secret "$secret_key" "$secret_value" "$project_identifier" "Imported from personal vault: $bw_item_name"
}

# Main command dispatcher
case "${1:-}" in
    "projects"|"p")
        list_projects
        ;;
    "secrets"|"s")
        if [ -z "${2:-}" ]; then
            echo "Usage: $0 secrets <project-name-or-id>"
            exit 1
        fi
        list_secrets "$2"
        ;;
    "get"|"g")
        if [ -z "${2:-}" ]; then
            echo "Usage: $0 get <secret-name> [project-name-or-id]"
            exit 1
        fi
        get_secret "$2" "${3:-}"
        ;;
    "create"|"c")
        if [ -z "${4:-}" ]; then
            echo "Usage: $0 create <key> <value> <project-name-or-id> [note]"
            exit 1
        fi
        create_secret "$2" "$3" "$4" "${5:-}"
        ;;
    "run"|"r")
        if [ -z "${2:-}" ]; then
            echo "Usage: $0 run [project-name-or-id] <command>"
            echo "       $0 run ./script.sh    # Run with all secrets"
            echo "       $0 run MyProject ./script.sh    # Run with specific project"
            exit 1
        fi
        
        # Check if first arg is a command or project
        if [ -f "$2" ] || command -v "$2" &> /dev/null || [[ "$2" == *"="* ]] || [[ "$2" == ./* ]]; then
            # First arg is a command
            run_with_secrets "" "$@"
        else
            # First arg is project, rest is command
            project="$2"
            shift 2
            run_with_secrets "$project" "$@"
        fi
        ;;
    "import"|"i")
        if [ -z "${4:-}" ]; then
            echo "Usage: $0 import <bw-item-name> <secret-key> <project-name-or-id>"
            exit 1
        fi
        import_from_bw "$2" "$3" "$4"
        ;;
    *)
        echo "Usage: $0 {projects|secrets|get|create|run|import}"
        echo ""
        echo "Commands:"
        echo "  projects (p)                              - List all projects"
        echo "  secrets (s) <project>                     - List secrets in project"
        echo "  get (g) <name> [project]                  - Get secret value"
        echo "  create (c) <key> <value> <project> [note] - Create secret"
        echo "  run (r) [project] <command>               - Run command with secrets"
        echo "  import (i) <bw-item> <key> <project>      - Import from personal vault"
        echo ""
        echo "Examples:"
        echo "  $0 projects"
        echo "  $0 secrets \"My Project\""
        echo "  $0 get DATABASE_URL"
        echo "  $0 create API_KEY \"abc123\" \"Production\""
        echo "  $0 run \"Development\" ./start-dev.sh"
        echo "  $0 import \"GitHub API\" GITHUB_TOKEN \"Development\""
        exit 1
        ;;
esac