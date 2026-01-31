#!/bin/bash

# Quick deployment script for Claude.ai MCP Server
# Run this on the target server (redleif-dev)

set -e

echo "🚀 Quick Deploy Claude.ai MCP Server"
echo "Current directory: $(pwd)"
echo "User: $(whoami)"
echo ""

# Check if we're on the right server
if [ ! -d "/home/redleif/Obsidian-Memory/brain" ]; then
    echo "❌ This doesn't look like the right server (no Obsidian-Memory directory found)"
    echo "Expected: /home/redleif/Obsidian-Memory/brain"
    exit 1
fi

VAULT_DIR="/home/redleif/Obsidian-Memory/brain"
SCRIPTS_DIR="$VAULT_DIR/skills/obsidian-memory/scripts"

echo "📁 Setting up directories..."
mkdir -p "$SCRIPTS_DIR"
cd "$SCRIPTS_DIR"

echo "📦 Installing Node.js dependencies..."
if [ ! -f "package.json" ]; then
    cat > package.json << 'EOF'
{
  "name": "obsidian-memory-mcp-server",
  "version": "1.0.0",
  "description": "Claude.ai compatible MCP server with OAuth 2.0",
  "main": "claude-ai-mcp-server.js",
  "scripts": {
    "start": "node claude-ai-mcp-server.js",
    "test": "node test-claude-ai-oauth.sh"
  },
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "dotenv": "^16.3.1"
  },
  "keywords": ["mcp", "obsidian", "claude.ai", "oauth2"],
  "author": "Jody Fielder",
  "license": "MIT"
}
EOF
fi

npm install

echo "🔧 Creating .env file..."
cat > .env << 'EOF'
# Claude.ai MCP Server Configuration
VAULT_PATH=/home/redleif/Obsidian-Memory/brain
PORT=3001
SERVER_URL=https://memory.redleif.dev
NODE_ENV=production
EOF

echo "📝 Files created, checking if running as root for service installation..."
if [[ $EUID -eq 0 ]]; then
    echo "🔧 Installing systemd service (running as root)..."
    
    # Stop old services
    systemctl stop obsidian-memory-mcp 2>/dev/null || true
    systemctl stop claude-ai-mcp 2>/dev/null || true
    
    # Install new service
    cp claude-ai-mcp.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable claude-ai-mcp
    systemctl start claude-ai-mcp
    
    echo "✅ Service installed and started"
    
    # Update nginx if needed
    echo "🌐 Updating nginx configuration..."
    NGINX_CONFIG="/etc/nginx/sites-available/memory.redleif.dev"
    
    if [ -f "$NGINX_CONFIG" ]; then
        # Backup original
        cp "$NGINX_CONFIG" "$NGINX_CONFIG.backup.$(date +%Y%m%d-%H%M%S)"
        
        # Check if OAuth endpoints already exist
        if ! grep -q "oauth-authorization-server" "$NGINX_CONFIG"; then
            echo "Adding OAuth endpoints to nginx..."
            
            # Add OAuth endpoints before /mcp location
            sed -i '/location \/mcp {/i\    # OAuth 2.0 endpoints for Claude.ai\
    location /.well-known/oauth-authorization-server {\
        proxy_pass http://127.0.0.1:3001;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
    }\
\
    location /register {\
        proxy_pass http://127.0.0.1:3001;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
    }\
\
    location /authorize {\
        proxy_pass http://127.0.0.1:3001;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
    }\
\
    location /token {\
        proxy_pass http://127.0.0.1:3001;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
    }\
' "$NGINX_CONFIG"
            
            # Test and reload nginx
            if nginx -t; then
                systemctl reload nginx
                echo "✅ Nginx updated and reloaded"
            else
                echo "❌ Nginx config error, restoring backup"
                mv "$NGINX_CONFIG.backup."* "$NGINX_CONFIG"
                exit 1
            fi
        else
            echo "✅ OAuth endpoints already configured in nginx"
        fi
    else
        echo "⚠️  Nginx config not found at $NGINX_CONFIG"
    fi
    
else
    echo "⚠️  Not running as root - service installation skipped"
    echo "💡 To install service, run: sudo $0"
    echo ""
    echo "🏃 Starting server manually for testing..."
    node claude-ai-mcp-server.js &
    SERVER_PID=$!
    echo "Server PID: $SERVER_PID"
    sleep 3
fi

echo ""
echo "🧪 Testing OAuth endpoints..."
sleep 2

# Test OAuth discovery
echo "Testing OAuth discovery..."
if curl -s -f "https://memory.redleif.dev/.well-known/oauth-authorization-server" >/dev/null; then
    echo "✅ OAuth discovery endpoint working"
else
    echo "⚠️  OAuth discovery not responding yet (may need a moment)"
fi

# Test client registration  
echo "Testing client registration..."
if curl -s -f -X POST "https://memory.redleif.dev/register" -H "Content-Type: application/json" -d '{"client_name":"Test"}' >/dev/null; then
    echo "✅ Client registration working"
else
    echo "⚠️  Client registration not responding yet"
fi

echo ""
echo "🎉 Deployment Complete!"
echo ""
echo "📊 Service Status:"
if [[ $EUID -eq 0 ]]; then
    systemctl status claude-ai-mcp --no-pager
else
    echo "   Manual mode - check process with: ps aux | grep claude-ai-mcp"
fi

echo ""
echo "🔗 Endpoints:"
echo "   OAuth Discovery: https://memory.redleif.dev/.well-known/oauth-authorization-server"
echo "   MCP Endpoint: https://memory.redleif.dev/mcp"
echo ""
echo "📱 Claude.ai Setup:"
echo "   1. Settings → Connectors → Add custom connector"
echo "   2. Name: Obsidian Memory"
echo "   3. URL: https://memory.redleif.dev/mcp"
echo "   4. OAuth: Leave credentials blank (dynamic registration)"
echo "   5. Connect!"
echo ""
echo "📋 Logs: journalctl -u claude-ai-mcp -f"