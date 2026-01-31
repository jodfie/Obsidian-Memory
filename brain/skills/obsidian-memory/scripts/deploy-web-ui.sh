#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🧠 Deploying Obsidian Memory Web UI${NC}"

# Variables
WEB_DIR="/opt/obsidian-memory-web"
NGINX_SITE="memory.redleif.dev"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root or with sudo${NC}"
   exit 1
fi

echo -e "${YELLOW}📁 Setting up web directory...${NC}"
# Create web directory if it doesn't exist
mkdir -p "$WEB_DIR"

# Copy web UI files
cp "$SCRIPT_DIR/web-ui.html" "$WEB_DIR/index.html"

# Set proper permissions
chown -R www-data:www-data "$WEB_DIR"
chmod -R 755 "$WEB_DIR"

echo -e "${YELLOW}🔧 Configuring nginx...${NC}"
# Copy nginx configuration
cp "$SCRIPT_DIR/nginx-memory.conf" "/etc/nginx/sites-available/$NGINX_SITE"

# Create symlink if it doesn't exist
if [ ! -L "/etc/nginx/sites-enabled/$NGINX_SITE" ]; then
    ln -s "/etc/nginx/sites-available/$NGINX_SITE" "/etc/nginx/sites-enabled/$NGINX_SITE"
    echo -e "${GREEN}✅ Created nginx site symlink${NC}"
fi

# Test nginx configuration
echo -e "${YELLOW}🧪 Testing nginx configuration...${NC}"
if nginx -t; then
    echo -e "${GREEN}✅ Nginx configuration is valid${NC}"
else
    echo -e "${RED}❌ Nginx configuration test failed${NC}"
    exit 1
fi

# Reload nginx
echo -e "${YELLOW}🔄 Reloading nginx...${NC}"
systemctl reload nginx

# Check if MCP server service exists and is running
echo -e "${YELLOW}🔍 Checking MCP server status...${NC}"
if systemctl is-active --quiet obsidian-memory-mcp; then
    echo -e "${GREEN}✅ MCP server is running${NC}"
else
    echo -e "${YELLOW}⚠️  MCP server is not running. Starting it...${NC}"
    
    # Check if service file exists
    if [ -f "/etc/systemd/system/obsidian-memory-mcp.service" ]; then
        systemctl start obsidian-memory-mcp
        systemctl enable obsidian-memory-mcp
        echo -e "${GREEN}✅ MCP server started${NC}"
    else
        echo -e "${RED}❌ MCP server service file not found. Run setup.sh first.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo -e ""
echo -e "Web UI: ${GREEN}https://memory.redleif.dev/${NC}"
echo -e "API endpoint: ${GREEN}https://memory.redleif.dev/mcp${NC}"
echo -e ""
echo -e "Next steps:"
echo -e "1. Test the web UI in your browser"
echo -e "2. Verify API connectivity with the search function"
echo -e "3. Check logs if needed: ${YELLOW}sudo journalctl -u obsidian-memory-mcp -f${NC}"