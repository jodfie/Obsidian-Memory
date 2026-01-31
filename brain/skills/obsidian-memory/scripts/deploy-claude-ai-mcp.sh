#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🧠 Deploying Claude.ai Compatible MCP Server${NC}"

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root or with sudo${NC}"
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="claude-ai-mcp"
OLD_SERVICE="obsidian-memory-mcp"

echo -e "${YELLOW}🛑 Stopping existing services...${NC}"
# Stop and disable old service if it exists
if systemctl is-active --quiet $OLD_SERVICE 2>/dev/null; then
    systemctl stop $OLD_SERVICE
    echo -e "${GREEN}✅ Stopped old MCP server${NC}"
fi

# Stop new service if it's already running
if systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
    systemctl stop $SERVICE_NAME
    echo -e "${GREEN}✅ Stopped Claude.ai MCP server${NC}"
fi

echo -e "${YELLOW}📦 Installing dependencies...${NC}"
cd "$SCRIPT_DIR"

# Ensure Node.js dependencies are installed
if [ ! -d "node_modules" ]; then
    npm install
fi

# Make server executable
chmod +x claude-ai-mcp-server.js

echo -e "${YELLOW}⚙️  Installing systemd service...${NC}"
# Copy service file
cp claude-ai-mcp.service "/etc/systemd/system/$SERVICE_NAME.service"

# Reload systemd
systemctl daemon-reload

# Enable and start service
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# Check status
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✅ Claude.ai MCP server is running${NC}"
else
    echo -e "${RED}❌ Failed to start Claude.ai MCP server${NC}"
    journalctl -u $SERVICE_NAME --lines=10
    exit 1
fi

echo -e "${YELLOW}🔧 Checking nginx configuration...${NC}"
# Check if nginx config needs updating for OAuth endpoints
NGINX_CONFIG="/etc/nginx/sites-available/memory.redleif.dev"

if [ -f "$NGINX_CONFIG" ]; then
    # Check if OAuth endpoints are already configured
    if ! grep -q "/.well-known/oauth-authorization-server" "$NGINX_CONFIG"; then
        echo -e "${YELLOW}📝 Updating nginx config for OAuth endpoints...${NC}"
        
        # Create backup
        cp "$NGINX_CONFIG" "$NGINX_CONFIG.backup.$(date +%Y%m%d-%H%M%S)"
        
        # Add OAuth endpoints before the existing /mcp location
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

        # Test nginx config
        if nginx -t; then
            systemctl reload nginx
            echo -e "${GREEN}✅ Updated and reloaded nginx configuration${NC}"
        else
            echo -e "${RED}❌ Nginx configuration error, restoring backup${NC}"
            mv "$NGINX_CONFIG.backup."* "$NGINX_CONFIG"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ Nginx OAuth endpoints already configured${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Nginx config not found, you'll need to configure it manually${NC}"
fi

echo -e "${YELLOW}🧪 Testing OAuth endpoints...${NC}"
sleep 2  # Give service a moment to fully start

# Test OAuth discovery endpoint
DISCOVERY_URL="https://memory.redleif.dev/.well-known/oauth-authorization-server"
if curl -s -f "$DISCOVERY_URL" >/dev/null; then
    echo -e "${GREEN}✅ OAuth discovery endpoint responding${NC}"
else
    echo -e "${YELLOW}⚠️  OAuth discovery endpoint not responding (may take a moment)${NC}"
fi

echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo -e ""
echo -e "📍 Service Status: ${GREEN}systemctl status $SERVICE_NAME${NC}"
echo -e "📍 Service Logs: ${GREEN}journalctl -u $SERVICE_NAME -f${NC}"
echo -e ""
echo -e "🔗 OAuth Discovery: ${GREEN}https://memory.redleif.dev/.well-known/oauth-authorization-server${NC}"
echo -e "🔗 Client Registration: ${GREEN}https://memory.redleif.dev/register${NC}"
echo -e "🔗 MCP Endpoint: ${GREEN}https://memory.redleif.dev/mcp${NC}"
echo -e ""
echo -e "📋 To connect in Claude.ai:"
echo -e "   1. Go to Settings → Connectors"
echo -e "   2. Add custom connector"
echo -e "   3. URL: ${YELLOW}https://memory.redleif.dev/mcp${NC}"
echo -e "   4. Leave OAuth credentials blank (uses dynamic registration)"