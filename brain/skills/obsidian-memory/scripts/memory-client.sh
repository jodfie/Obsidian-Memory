#!/bin/bash

# Obsidian-Memory HTTP Client
# Wrapper script for easier interaction with the MCP server

set -e

# Configuration
MEMORY_URL="${OBSIDIAN_MEMORY_URL:-http://localhost:3001}"
API_KEY="${OBSIDIAN_MEMORY_API_KEY:-}"

if [ -z "$API_KEY" ]; then
    echo "❌ OBSIDIAN_MEMORY_API_KEY environment variable not set"
    exit 1
fi

# Helper function to make MCP requests
mcp_request() {
    local method="$1"
    local params="$2"
    
    curl -s -X POST "$MEMORY_URL/mcp" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"method\":\"$method\",\"params\":$params}"
}

# Commands
case "${1:-help}" in
    search|s)
        if [ -z "$2" ]; then
            echo "Usage: $0 search \"query\" [max_results]"
            exit 1
        fi
        
        query="$2"
        max_results="${3:-10}"
        
        echo "🔍 Searching for: $query"
        mcp_request "memory_search" "{\"query\":\"$query\",\"maxResults\":$max_results}" \
            | jq -r '.results[]? | "📍 \(.path):\(.line) - \(.content)"' \
            || echo "No results found"
        ;;
        
    get|g)
        if [ -z "$2" ]; then
            echo "Usage: $0 get \"path\" [from_line] [num_lines]"
            exit 1
        fi
        
        path="$2"
        from_line="${3:-null}"
        num_lines="${4:-null}"
        
        echo "📄 Reading: $path"
        if [ "$from_line" != "null" ]; then
            params="{\"path\":\"$path\",\"from\":$from_line,\"lines\":$num_lines}"
        else
            params="{\"path\":\"$path\"}"
        fi
        
        mcp_request "memory_get" "$params" \
            | jq -r '.content // .error // "No content"'
        ;;
        
    write|w)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Usage: $0 write \"path\" \"content\" [append]"
            exit 1
        fi
        
        path="$2"
        content="$3"
        append="${4:-false}"
        
        echo "✍️ Writing to: $path"
        mcp_request "memory_write" "{\"path\":\"$path\",\"content\":\"$content\",\"append\":$append}" \
            | jq -r '.success // .error // "Unknown result"'
        ;;
        
    log|l)
        if [ -z "$2" ]; then
            echo "Usage: $0 log \"content\" [category]"
            exit 1
        fi
        
        content="$2"
        category="${3:-Notes}"
        
        echo "📝 Logging: $content"
        mcp_request "memory_log" "{\"content\":\"$content\",\"category\":\"$category\"}" \
            | jq -r '(.success and "✅ Logged successfully") // .error // "Unknown result"'
        ;;
        
    health|h)
        echo "🏥 Checking server health..."
        curl -s "$MEMORY_URL/health" | jq . || echo "❌ Health check failed"
        ;;
        
    today|t)
        today=$(date +%Y-%m-%d)
        echo "📅 Today's memory: memory/$today.md"
        mcp_request "memory_get" "{\"path\":\"memory/$today.md\"}" \
            | jq -r '.content // "No entries for today"'
        ;;
        
    recent|r)
        days="${2:-7}"
        echo "📋 Recent activity (last $days days):"
        
        for i in $(seq 0 $((days-1))); do
            date_str=$(date -d "-$i days" +%Y-%m-%d)
            echo "--- $date_str ---"
            mcp_request "memory_get" "{\"path\":\"memory/$date_str.md\"}" \
                | jq -r '.content // "No entries"' \
                | head -10
            echo ""
        done
        ;;
        
    help)
        cat << 'EOF'
🧠 Obsidian-Memory Client

Usage: memory-client.sh <command> [args...]

Commands:
  search|s  "query" [max]     Search memory files
  get|g     "path" [line] [n] Read file content  
  write|w   "path" "content"  Write to file
  log|l     "content" [cat]   Quick log entry
  health|h                    Check server health
  today|t                     Show today's memory
  recent|r  [days]            Show recent activity
  help                        Show this help

Environment:
  OBSIDIAN_MEMORY_URL      Server URL (default: http://localhost:3001)
  OBSIDIAN_MEMORY_API_KEY  Authentication key (required)

Examples:
  memory-client.sh search "browser automation"
  memory-client.sh log "Completed important task" "Accomplishments"
  memory-client.sh get "MEMORY.md" 1 20
  memory-client.sh today
EOF
        ;;
        
    *)
        echo "❌ Unknown command: $1"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac