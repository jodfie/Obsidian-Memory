#!/bin/bash
# obtain-tokens.sh
# Run this ONCE locally to obtain OAuth tokens, then use them in CI/CD
# 
# Usage: ./obtain-tokens.sh <MCP_SERVER_URL>
# Example: ./obtain-tokens.sh https://memory.example.com/sse

set -e

MCP_URL="${1:-}"

if [ -z "$MCP_URL" ]; then
    echo "Usage: $0 <MCP_SERVER_URL>"
    echo "Example: $0 https://memory.example.com/sse"
    exit 1
fi

echo "=== MCP Token Obtainer ==="
echo ""
echo "This will open a browser for OAuth authentication."
echo "After authenticating, tokens will be saved to ~/.mcp-auth/"
echo ""
echo "Server: $MCP_URL"
echo ""

# Use mcp-remote which handles OAuth flow and caches tokens
echo "Starting OAuth flow..."
echo "Press Ctrl+C after authentication completes."
echo ""

# Run mcp-remote in foreground - it will open browser for OAuth
# User completes auth, then presses Ctrl+C
npx mcp-remote "$MCP_URL" &
MCP_PID=$!

# Wait for user to complete OAuth
echo ""
echo "Browser should open for authentication..."
echo "After completing auth in browser, press Enter here to continue."
read -r

# Kill mcp-remote
kill $MCP_PID 2>/dev/null || true

# Check for saved tokens
AUTH_DIR="$HOME/.mcp-auth"

if [ -d "$AUTH_DIR" ]; then
    echo ""
    echo "=== Tokens Saved ==="
    echo "Location: $AUTH_DIR"
    echo ""
    
    # Show what's there (without exposing actual tokens)
    ls -la "$AUTH_DIR"
    
    echo ""
    echo "=== Export Commands for CI/CD ==="
    echo ""
    
    # Extract token from the saved files
    HOST=$(echo "$MCP_URL" | sed -E 's|https?://([^/:]+).*|\1|')
    
    if [ -f "$AUTH_DIR/tokens.json" ]; then
        TOKEN=$(cat "$AUTH_DIR/tokens.json" | jq -r ".[\"$HOST\"].access_token // empty")
        REFRESH=$(cat "$AUTH_DIR/tokens.json" | jq -r ".[\"$HOST\"].refresh_token // empty")
        
        if [ -n "$TOKEN" ]; then
            echo "# Add these to your CI/CD secrets:"
            echo "MCP_ACCESS_TOKEN=$TOKEN"
            [ -n "$REFRESH" ] && echo "MCP_REFRESH_TOKEN=$REFRESH"
            
            echo ""
            echo "# Or copy the auth directory for volume mounting:"
            echo "cp -r $AUTH_DIR ./mcp-auth"
        fi
    fi
    
    # Also check for individual server files
    for f in "$AUTH_DIR"/*.json; do
        [ -f "$f" ] && echo "Found auth file: $f"
    done
    
else
    echo ""
    echo "ERROR: No tokens found in $AUTH_DIR"
    echo "Authentication may have failed. Try again."
    exit 1
fi

echo ""
echo "=== Done ==="
echo "Use these tokens in your CI/CD pipeline by setting environment variables"
echo "or mounting the $AUTH_DIR directory into your container."
