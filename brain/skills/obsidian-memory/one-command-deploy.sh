#!/bin/bash

# One-Command Claude.ai MCP Server Deployment
# Run this on redleif-dev server as root: sudo bash <(curl -s URL)

set -e

echo "🧠 Claude.ai MCP Server - One Command Deploy"
echo "============================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Please run as root: sudo $0"
   exit 1
fi

# Set paths
VAULT_DIR="/home/redleif/Obsidian-Memory/brain"
SCRIPTS_DIR="$VAULT_DIR/skills/obsidian-memory/scripts"

echo "📁 Setting up directories..."
mkdir -p "$SCRIPTS_DIR"
cd "$SCRIPTS_DIR"

# Stop any existing services
echo "🛑 Stopping existing services..."
systemctl stop obsidian-memory-mcp 2>/dev/null || true
systemctl stop claude-ai-mcp 2>/dev/null || true

echo "📦 Creating package.json..."
cat > package.json << 'EOF'
{
  "name": "obsidian-memory-mcp-server",
  "version": "1.0.0",
  "description": "Claude.ai compatible MCP server with OAuth 2.0",
  "main": "claude-ai-mcp-server.js",
  "scripts": {
    "start": "node claude-ai-mcp-server.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "dotenv": "^16.3.1"
  },
  "author": "Jody Fielder",
  "license": "MIT"
}
EOF

echo "📝 Creating .env file..."
cat > .env << 'EOF'
VAULT_PATH=/home/redleif/Obsidian-Memory/brain
PORT=3001
SERVER_URL=https://memory.redleif.dev
NODE_ENV=production
EOF

echo "🛠️ Installing Node.js dependencies..."
npm install

echo "🚀 Creating Claude.ai MCP Server..."
cat > claude-ai-mcp-server.js << 'JSEOF'
#!/usr/bin/env node

/**
 * Claude.ai Compatible MCP Server with OAuth 2.0
 * Implements RFC 8414 + RFC 7591 + MCP protocol for Claude.ai
 */

const express = require('express');
const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');
const { promisify } = require('util');
const { exec } = require('child_process');
require('dotenv').config();

const execAsync = promisify(exec);

// Configuration
const PORT = process.env.PORT || 3001;
const VAULT_PATH = process.env.VAULT_PATH || '/home/redleif/Obsidian-Memory/brain';
const SERVER_URL = process.env.SERVER_URL || 'https://memory.redleif.dev';

class ClaudeAIMCPServer {
  constructor(vaultPath) {
    this.vaultPath = vaultPath;
    this.memoryDir = path.join(vaultPath, 'memory');
    
    // OAuth state management
    this.clients = new Map();
    this.authCodes = new Map();
    this.accessTokens = new Map();
    
    this.initializeDirectories();
  }

  async initializeDirectories() {
    try {
      await fs.mkdir(this.memoryDir, { recursive: true });
      console.log('📁 Initialized directories');
    } catch (error) {
      console.error('❌ Failed to initialize directories:', error);
    }
  }

  // RFC 8414: OAuth Authorization Server Metadata
  getAuthorizationServerMetadata() {
    return {
      issuer: SERVER_URL,
      authorization_endpoint: `${SERVER_URL}/authorize`,
      token_endpoint: `${SERVER_URL}/token`,
      registration_endpoint: `${SERVER_URL}/register`,
      response_types_supported: ['code'],
      grant_types_supported: ['authorization_code'],
      code_challenge_methods_supported: ['S256'],
      token_endpoint_auth_methods_supported: ['none'],
      scopes_supported: ['mcp']
    };
  }

  // RFC 7591: Dynamic Client Registration
  async registerClient(registration) {
    const clientId = crypto.randomUUID();
    const client = {
      client_id: clientId,
      client_name: registration.client_name || 'Claude.ai',
      redirect_uris: registration.redirect_uris || [],
      grant_types: ['authorization_code'],
      response_types: ['code'],
      scope: 'mcp',
      created_at: Date.now()
    };
    
    this.clients.set(clientId, client);
    
    return {
      client_id: clientId,
      client_name: client.client_name,
      redirect_uris: client.redirect_uris,
      grant_types: client.grant_types,
      response_types: client.response_types,
      scope: client.scope
    };
  }

  // Generate PKCE code challenge
  generateCodeChallenge(codeVerifier) {
    return crypto.createHash('sha256').update(codeVerifier).digest('base64url');
  }

  // OAuth Authorization
  async authorizeClient(params) {
    const { client_id, redirect_uri, code_challenge, code_challenge_method, state } = params;
    
    if (!this.clients.has(client_id)) {
      throw new Error('Invalid client_id');
    }
    
    if (code_challenge_method !== 'S256') {
      throw new Error('Unsupported code_challenge_method');
    }
    
    // Generate authorization code
    const authCode = crypto.randomBytes(32).toString('hex');
    const expiresAt = Date.now() + 10 * 60 * 1000; // 10 minutes
    
    this.authCodes.set(authCode, {
      clientId: client_id,
      redirectUri: redirect_uri,
      codeChallenge: code_challenge,
      state,
      expiresAt
    });
    
    // Return redirect URL
    const redirectUrl = new URL(redirect_uri);
    redirectUrl.searchParams.set('code', authCode);
    redirectUrl.searchParams.set('state', state);
    
    return redirectUrl.toString();
  }

  // OAuth Token Exchange
  async exchangeToken(params) {
    const { grant_type, code, code_verifier, client_id, redirect_uri } = params;
    
    if (grant_type !== 'authorization_code') {
      throw new Error('Unsupported grant_type');
    }
    
    if (!this.authCodes.has(code)) {
      throw new Error('Invalid authorization code');
    }
    
    const authInfo = this.authCodes.get(code);
    
    // Verify expiration
    if (Date.now() > authInfo.expiresAt) {
      this.authCodes.delete(code);
      throw new Error('Authorization code expired');
    }
    
    // Verify PKCE
    const expectedChallenge = this.generateCodeChallenge(code_verifier);
    if (expectedChallenge !== authInfo.codeChallenge) {
      throw new Error('Invalid code_verifier');
    }
    
    // Generate access token
    const accessToken = crypto.randomBytes(32).toString('hex');
    const expiresIn = 3600; // 1 hour
    const expiresAt = Date.now() + expiresIn * 1000;
    
    this.accessTokens.set(accessToken, {
      clientId: client_id,
      expiresAt
    });
    
    // Clean up auth code
    this.authCodes.delete(code);
    
    return {
      access_token: accessToken,
      token_type: 'Bearer',
      expires_in: expiresIn
    };
  }

  // Verify access token
  verifyAccessToken(token) {
    if (!this.accessTokens.has(token)) {
      throw new Error('Invalid access token');
    }
    
    const tokenInfo = this.accessTokens.get(token);
    if (Date.now() > tokenInfo.expiresAt) {
      this.accessTokens.delete(token);
      throw new Error('Access token expired');
    }
    
    return tokenInfo;
  }

  // MCP Protocol Implementation
  async handleMCPRequest(method, params = {}) {
    switch (method) {
      case 'tools/list':
        return this.listTools();
      case 'tools/call':
        return this.callTool(params.name, params.arguments || {});
      default:
        throw new Error(`Unknown method: ${method}`);
    }
  }

  listTools() {
    return {
      tools: [
        {
          name: 'mem_search',
          description: 'Search memory for information',
          inputSchema: {
            type: 'object',
            properties: {
              query: { type: 'string', description: 'Search query' },
              maxResults: { type: 'number', description: 'Maximum results', default: 10 }
            },
            required: ['query']
          }
        },
        {
          name: 'mem_read',
          description: 'Read content from memory file',
          inputSchema: {
            type: 'object',
            properties: {
              path: { type: 'string', description: 'File path to read' }
            },
            required: ['path']
          }
        },
        {
          name: 'mem_write',
          description: 'Write content to memory file',
          inputSchema: {
            type: 'object',
            properties: {
              path: { type: 'string', description: 'File path to write' },
              content: { type: 'string', description: 'Content to write' },
              append: { type: 'boolean', description: 'Append or overwrite', default: false }
            },
            required: ['path', 'content']
          }
        }
      ]
    };
  }

  async callTool(name, args) {
    switch (name) {
      case 'mem_search':
        return this.searchMemory(args.query, args.maxResults || 10);
      case 'mem_read':
        return this.readMemory(args.path);
      case 'mem_write':
        return this.writeMemory(args.path, args.content, args.append);
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  }

  async searchMemory(query, maxResults = 10) {
    try {
      const cmd = `find "${this.vaultPath}" -name "*.md" -type f | xargs grep -i -n "${query}" | head -${maxResults}`;
      const { stdout } = await execAsync(cmd);
      
      const results = stdout.trim().split('\n').filter(line => line).map(line => {
        const [filePath, lineNumber, ...contentParts] = line.split(':');
        return {
          path: path.relative(this.vaultPath, filePath),
          line: parseInt(lineNumber),
          content: contentParts.join(':').trim()
        };
      });
      
      return { results };
    } catch (error) {
      return { results: [], error: error.message };
    }
  }

  async readMemory(filePath) {
    try {
      const fullPath = path.resolve(this.vaultPath, filePath);
      
      if (!fullPath.startsWith(this.vaultPath)) {
        throw new Error('Access denied - path outside vault');
      }
      
      const content = await fs.readFile(fullPath, 'utf8');
      return { path: filePath, content };
    } catch (error) {
      return { error: error.message };
    }
  }

  async writeMemory(filePath, content, append = false) {
    try {
      const fullPath = path.resolve(this.vaultPath, filePath);
      
      if (!fullPath.startsWith(this.vaultPath)) {
        throw new Error('Access denied - path outside vault');
      }
      
      await fs.mkdir(path.dirname(fullPath), { recursive: true });
      
      if (append) {
        await fs.appendFile(fullPath, '\n' + content);
      } else {
        await fs.writeFile(fullPath, content);
      }
      
      return { success: true, path: filePath };
    } catch (error) {
      return { error: error.message };
    }
  }
}

// Express server setup
const app = express();
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// CORS for Claude.ai
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// Initialize server
const mcpServer = new ClaudeAIMCPServer(VAULT_PATH);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// RFC 8414: OAuth Authorization Server Metadata
app.get('/.well-known/oauth-authorization-server', (req, res) => {
  res.json(mcpServer.getAuthorizationServerMetadata());
});

// RFC 7591: Dynamic Client Registration
app.post('/register', async (req, res) => {
  try {
    const client = await mcpServer.registerClient(req.body);
    res.json(client);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// OAuth Authorization
app.get('/authorize', async (req, res) => {
  try {
    const redirectUrl = await mcpServer.authorizeClient(req.query);
    res.redirect(redirectUrl);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// OAuth Token Exchange
app.post('/token', async (req, res) => {
  try {
    const token = await mcpServer.exchangeToken(req.body);
    res.json(token);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// MCP Protocol Endpoint
app.post('/mcp', async (req, res) => {
  try {
    // Extract Bearer token
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Missing authorization header' });
    }
    
    const token = authHeader.substring(7);
    mcpServer.verifyAccessToken(token);
    
    // Handle MCP request
    const { method, params } = req.body;
    const result = await mcpServer.handleMCPRequest(method, params);
    
    res.json(result);
  } catch (error) {
    res.status(401).json({ error: error.message });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`🧠 Claude.ai MCP Server running on port ${PORT}`);
  console.log(`📍 OAuth Discovery: ${SERVER_URL}/.well-known/oauth-authorization-server`);
  console.log(`🚀 MCP Endpoint: ${SERVER_URL}/mcp`);
});

process.on('SIGTERM', () => {
  console.log('🛑 Shutting down gracefully');
  process.exit(0);
});
JSEOF

echo "⚙️ Creating systemd service..."
cat > claude-ai-mcp.service << 'SERVICEEOF'
[Unit]
Description=Claude.ai Compatible Obsidian-Memory MCP Server with OAuth 2.0
After=network.target

[Service]
Type=simple
User=redleif
Group=redleif
WorkingDirectory=/home/redleif/Obsidian-Memory/brain/skills/obsidian-memory/scripts
ExecStart=/usr/bin/node claude-ai-mcp-server.js
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment=NODE_ENV=production
Environment=VAULT_PATH=/home/redleif/Obsidian-Memory/brain
Environment=PORT=3001
Environment=SERVER_URL=https://memory.redleif.dev

NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/redleif/Obsidian-Memory/brain

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo "🔧 Installing and starting service..."
chmod +x claude-ai-mcp-server.js
cp claude-ai-mcp.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable claude-ai-mcp
systemctl start claude-ai-mcp

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
        echo "✅ OAuth endpoints already configured"
    fi
fi

echo ""
echo "🧪 Testing endpoints..."
sleep 3

# Test OAuth discovery
if curl -s -f "https://memory.redleif.dev/.well-known/oauth-authorization-server" >/dev/null; then
    echo "✅ OAuth discovery working"
else
    echo "⚠️  OAuth discovery not responding (may need a moment)"
fi

echo ""
echo "🎉 DEPLOYMENT COMPLETE! 🎉"
echo "=========================="
echo ""
echo "📊 Service Status:"
systemctl status claude-ai-mcp --no-pager -l
echo ""
echo "🔗 Endpoints Available:"
echo "   OAuth Discovery: https://memory.redleif.dev/.well-known/oauth-authorization-server"
echo "   MCP Endpoint: https://memory.redleif.dev/mcp"
echo ""
echo "📱 Connect in Claude.ai:"
echo "   1. Settings → Connectors → Add Custom Connector"
echo "   2. Name: Obsidian Memory"
echo "   3. URL: https://memory.redleif.dev/mcp"
echo "   4. OAuth: Leave credentials blank (dynamic registration)"
echo "   5. Click Connect!"
echo ""
echo "📋 Useful Commands:"
echo "   View logs: journalctl -u claude-ai-mcp -f"
echo "   Restart: systemctl restart claude-ai-mcp"
echo "   Status: systemctl status claude-ai-mcp"
echo ""
echo "🚀 Ready to connect from Claude.ai! 🧠"