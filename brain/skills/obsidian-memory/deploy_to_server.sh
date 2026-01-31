#!/bin/bash

# Deploy Claude.ai MCP Server to redleif-dev
# This script copies files and runs deployment

set -e

echo "🚀 Deploying Claude.ai MCP Server to redleif-dev"

SERVER="redleif-dev"
SERVER_PATH="/home/redleif/Obsidian-Memory/brain/skills/obsidian-memory/scripts"
LOCAL_PATH="./skills/obsidian-memory/scripts"

# Files to copy
FILES=(
    "claude-ai-mcp-server.js"
    "claude-ai-mcp.service"
    "quick-deploy.sh"
    "test-claude-ai-oauth.sh"
    "DEPLOY_INSTRUCTIONS.md"
    "package.json"
)

echo "📁 Copying files to server..."

# Create remote directory
ssh $SERVER "mkdir -p $SERVER_PATH"

# Copy files
for file in "${FILES[@]}"; do
    echo "  Copying $file..."
    scp "$LOCAL_PATH/$file" "$SERVER:$SERVER_PATH/"
done

echo "🔧 Making scripts executable..."
ssh $SERVER "chmod +x $SERVER_PATH/*.sh"

echo "🚀 Running deployment on server..."
ssh $SERVER "cd $SERVER_PATH && sudo ./quick-deploy.sh"

echo "🧪 Testing deployment..."
ssh $SERVER "cd $SERVER_PATH && ./test-claude-ai-oauth.sh"

echo "✅ Deployment complete!"
echo ""
echo "🔗 Your Claude.ai MCP server is ready at:"
echo "   https://memory.redleif.dev/mcp"
echo ""
echo "📱 To connect in Claude.ai:"
echo "   Settings → Connectors → Add Custom Connector"
echo "   URL: https://memory.redleif.dev/mcp"
echo "   OAuth: Leave blank (dynamic registration)"