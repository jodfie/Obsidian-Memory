#!/bin/bash
set -e

# MCP Test Harness Entrypoint
# Handles token setup and test execution

echo "=== MCP Test Harness ==="
echo "Server URL: ${MCP_SERVER_URL:-not set}"
echo "Token present: $([ -n "$MCP_ACCESS_TOKEN" ] && echo "yes" || echo "no")"

# Validate required environment
validate_env() {
    if [ -z "$MCP_SERVER_URL" ]; then
        echo "ERROR: MCP_SERVER_URL is required"
        exit 1
    fi
}

# Setup auth tokens from environment or mounted secrets
setup_auth() {
    echo "Setting up authentication..."
    
    # Check for token in environment
    if [ -n "$MCP_ACCESS_TOKEN" ]; then
        echo "Using token from MCP_ACCESS_TOKEN environment variable"
        
        # Create auth file for mcp-remote compatibility
        mkdir -p /root/.mcp-auth
        
        # Extract hostname for token storage
        HOST=$(echo "$MCP_SERVER_URL" | sed -E 's|https?://([^/:]+).*|\1|')
        
        cat > /root/.mcp-auth/tokens.json << EOF
{
  "${HOST}": {
    "access_token": "${MCP_ACCESS_TOKEN}",
    "refresh_token": "${MCP_REFRESH_TOKEN:-}",
    "token_type": "Bearer",
    "expires_at": "2099-12-31T23:59:59Z"
  }
}
EOF
        echo "Auth tokens configured for ${HOST}"
        return 0
    fi
    
    # Check for mounted auth directory
    if [ -f "/root/.mcp-auth/tokens.json" ]; then
        echo "Using mounted auth tokens from /root/.mcp-auth/tokens.json"
        return 0
    fi
    
    # Check for Cloudflare service token auth
    if [ -n "$CF_ACCESS_CLIENT_ID" ] && [ -n "$CF_ACCESS_CLIENT_SECRET" ]; then
        echo "Using Cloudflare Access service token"
        export MCP_AUTH_TYPE="cf-service-token"
        return 0
    fi
    
    echo "WARNING: No authentication configured - tests may fail"
    return 0
}

# Run the test suite
run_tests() {
    echo ""
    echo "=== Running MCP Server Tests ==="
    
    # Run the Node.js test runner
    node /app/scripts/test-runner.js
    
    TEST_EXIT=$?
    
    echo ""
    echo "=== Test Results ==="
    
    if [ -f "/app/results/summary.json" ]; then
        cat /app/results/summary.json | jq '.'
    fi
    
    return $TEST_EXIT
}

# List available tools on the server
list_tools() {
    echo "=== Listing Tools ==="
    node /app/scripts/list-tools.js
}

# Test a specific tool
test_tool() {
    TOOL_NAME=$1
    shift
    echo "=== Testing Tool: $TOOL_NAME ==="
    node /app/scripts/test-tool.js "$TOOL_NAME" "$@"
}

# Interactive mode - starts Inspector UI
interactive() {
    echo "=== Starting Interactive Mode ==="
    echo "MCP Inspector will be available at http://localhost:6274"
    
    if [ -n "$MCP_ACCESS_TOKEN" ]; then
        npx @modelcontextprotocol/inspector \
            --connect "$MCP_SERVER_URL" \
            --bearer-token "$MCP_ACCESS_TOKEN"
    else
        npx @modelcontextprotocol/inspector
    fi
}

# Main command handler
case "${1:-run-tests}" in
    run-tests)
        validate_env
        setup_auth
        run_tests
        ;;
    list-tools)
        validate_env
        setup_auth
        list_tools
        ;;
    test-tool)
        validate_env
        setup_auth
        shift
        test_tool "$@"
        ;;
    interactive)
        setup_auth
        interactive
        ;;
    shell)
        exec /bin/bash
        ;;
    *)
        echo "Unknown command: $1"
        echo "Usage: run-tests | list-tools | test-tool <name> | interactive | shell"
        exit 1
        ;;
esac
