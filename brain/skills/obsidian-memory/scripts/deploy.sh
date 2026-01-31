#!/bin/bash

# Obsidian-Memory MCP Server Deployment Script
# Deploys the MCP server to production environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="/home/redleif/obsidian-memory-mcp"
SERVICE_NAME="obsidian-memory-mcp"

echo "🚀 Deploying Obsidian-Memory MCP Server..."

# Create deployment directory
sudo mkdir -p "$DEPLOY_DIR"
sudo chown redleif:redleif "$DEPLOY_DIR"

# Copy server files
echo "📁 Copying server files..."
cp "$SCRIPT_DIR/enhanced-mcp-server.js" "$DEPLOY_DIR/mcp-server.js"
cp "$SCRIPT_DIR/package.json" "$DEPLOY_DIR/"

# Install dependencies
echo "📦 Installing production dependencies..."
cd "$DEPLOY_DIR"
npm install --production

# Set up environment
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    echo "📝 Creating production environment file..."
    API_KEY=$(openssl rand -hex 32)
    cat > "$DEPLOY_DIR/.env" << EOF
VAULT_PATH=/home/redleif/Obsidian-Memory/brain
PORT=3001
MCP_API_KEY=$API_KEY
NODE_ENV=production
EOF
    echo "✅ Created .env with API key: $API_KEY"
fi

# Install systemd service
echo "⚙️  Installing systemd service..."
sudo cp "$SCRIPT_DIR/$SERVICE_NAME.service" "/etc/systemd/system/"
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# Wait for service to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service is running!"
    
    # Test health endpoint
    if curl -s "http://localhost:3001/health" > /dev/null; then
        echo "✅ Health check passed!"
    else
        echo "⚠️  Health check failed - service may still be starting"
    fi
    
    echo ""
    echo "🎯 Deployment complete!"
    echo "📊 Service status: sudo systemctl status $SERVICE_NAME"
    echo "📋 Service logs: sudo journalctl -u $SERVICE_NAME -f"
    echo "🔗 API endpoint: http://localhost:3001/mcp"
    echo "🔑 API key: $(grep MCP_API_KEY $DEPLOY_DIR/.env | cut -d= -f2)"
else
    echo "❌ Service failed to start!"
    echo "🔍 Check logs: sudo journalctl -u $SERVICE_NAME -n 20"
    exit 1
fi