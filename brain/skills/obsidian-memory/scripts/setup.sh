#!/bin/bash

# Obsidian-Memory MCP Server Setup Script
# Sets up and starts the HTTPS MCP server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$SCRIPT_DIR"

echo "🧠 Setting up Obsidian-Memory MCP Server..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js first."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
cd "$SERVER_DIR"
npm install

# Set default environment variables
export VAULT_PATH="${VAULT_PATH:-/home/redleif/Obsidian-Memory/brain}"
export PORT="${PORT:-3001}"
export MCP_API_KEY="${MCP_API_KEY:-$(openssl rand -hex 32)}"

# Create .env file if it doesn't exist
if [ ! -f "$SERVER_DIR/.env" ]; then
    echo "📝 Creating .env file..."
    cat > "$SERVER_DIR/.env" << EOF
# Obsidian-Memory MCP Server Configuration
VAULT_PATH=$VAULT_PATH
PORT=$PORT
MCP_API_KEY=$MCP_API_KEY
NODE_ENV=production
EOF
    echo "✅ Created .env file with generated API key"
else
    echo "ℹ️  Using existing .env file"
fi

# Make server executable
chmod +x "$SERVER_DIR/mcp-server.js"

echo "✅ Setup complete!"
echo ""
echo "🚀 To start the server:"
echo "   cd $SERVER_DIR && npm start"
echo ""
echo "🔗 Server will run at: http://localhost:$PORT"
echo "🔑 API Key: $MCP_API_KEY"
echo "📁 Vault Path: $VAULT_PATH"
echo ""
echo "📋 Health check: curl http://localhost:$PORT/health"