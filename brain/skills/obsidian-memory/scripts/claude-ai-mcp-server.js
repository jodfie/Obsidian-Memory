#!/usr/bin/env node

/**
 * Claude.ai Compatible MCP Server with OAuth 2.0
 * Implements full RFC 8414 + RFC 7591 + MCP protocol
 * For use with Claude.ai remote MCP connections
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
    this.memoryFile = path.join(vaultPath, 'MEMORY.md');
    
    // OAuth state management
    this.clients = new Map(); // clientId -> client info
    this.authCodes = new Map(); // code -> { clientId, codeChallenge, expiresAt }
    this.accessTokens = new Map(); // token -> { clientId, expiresAt, scope }
    
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

  // RFC 8414: OAuth 2.0 Authorization Server Metadata
  getAuthorizationServerMetadata() {
    return {
      issuer: SERVER_URL,
      authorization_endpoint: `${SERVER_URL}/authorize`,
      token_endpoint: `${SERVER_URL}/token`,
      registration_endpoint: `${SERVER_URL}/register`,
      jwks_uri: `${SERVER_URL}/.well-known/jwks.json`,
      response_types_supported: ['code'],
      grant_types_supported: ['authorization_code'],
      code_challenge_methods_supported: ['S256'],
      token_endpoint_auth_methods_supported: ['none', 'client_secret_basic'],
      scopes_supported: ['mcp'],
      redirect_uris_supported: true
    };
  }

  // RFC 7591: Dynamic Client Registration
  async registerClient(registration) {
    const clientId = crypto.randomUUID();
    const clientSecret = crypto.randomBytes(32).toString('hex');
    
    const client = {
      client_id: clientId,
      client_secret: clientSecret,
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
      client_secret: clientSecret,
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
    const { client_id, redirect_uri, code_challenge, code_challenge_method, state, scope } = params;
    
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
      scope: scope || 'mcp',
      expiresAt
    });
    
    // Return authorization code (normally would redirect to redirect_uri)
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
    
    // Verify client and redirect URI
    if (authInfo.clientId !== client_id || authInfo.redirectUri !== redirect_uri) {
      throw new Error('Client mismatch');
    }
    
    // Generate access token
    const accessToken = crypto.randomBytes(32).toString('hex');
    const expiresIn = 3600; // 1 hour
    const expiresAt = Date.now() + expiresIn * 1000;
    
    this.accessTokens.set(accessToken, {
      clientId: client_id,
      scope: authInfo.scope,
      expiresAt
    });
    
    // Clean up auth code
    this.authCodes.delete(code);
    
    return {
      access_token: accessToken,
      token_type: 'Bearer',
      expires_in: expiresIn,
      scope: authInfo.scope
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
              maxResults: { type: 'number', description: 'Maximum results to return', default: 10 }
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
              path: { type: 'string', description: 'File path to read' },
              lines: { type: 'number', description: 'Number of lines to read' },
              offset: { type: 'number', description: 'Line offset to start from' }
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
              append: { type: 'boolean', description: 'Whether to append or overwrite', default: false }
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
        return this.readMemory(args.path, args.lines, args.offset);
      
      case 'mem_write':
        return this.writeMemory(args.path, args.content, args.append);
      
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  }

  async searchMemory(query, maxResults = 10) {
    try {
      // Simple grep-based search across markdown files
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

  async readMemory(filePath, lines, offset) {
    try {
      const fullPath = path.resolve(this.vaultPath, filePath);
      
      // Security check - ensure we're within vault
      if (!fullPath.startsWith(this.vaultPath)) {
        throw new Error('Access denied - path outside vault');
      }
      
      const content = await fs.readFile(fullPath, 'utf8');
      const allLines = content.split('\n');
      
      let resultLines = allLines;
      if (offset) {
        resultLines = allLines.slice(offset - 1);
      }
      if (lines) {
        resultLines = resultLines.slice(0, lines);
      }
      
      return {
        path: filePath,
        content: resultLines.join('\n'),
        totalLines: allLines.length
      };
    } catch (error) {
      return { error: error.message };
    }
  }

  async writeMemory(filePath, content, append = false) {
    try {
      const fullPath = path.resolve(this.vaultPath, filePath);
      
      // Security check
      if (!fullPath.startsWith(this.vaultPath)) {
        throw new Error('Access denied - path outside vault');
      }
      
      // Ensure directory exists
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

// OAuth Authorization Endpoint
app.get('/authorize', async (req, res) => {
  try {
    // For simplicity, auto-approve (in production, show consent page)
    const redirectUrl = await mcpServer.authorizeClient(req.query);
    res.redirect(redirectUrl);
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

// OAuth Token Endpoint
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
      return res.status(401).json({ error: 'Missing or invalid authorization header' });
    }
    
    const token = authHeader.substring(7);
    mcpServer.verifyAccessToken(token); // This will throw if invalid
    
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
  console.log(`🔐 Client Registration: ${SERVER_URL}/register`);
  console.log(`🚀 MCP Endpoint: ${SERVER_URL}/mcp`);
  console.log(`📁 Vault Path: ${VAULT_PATH}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('🛑 Received SIGTERM, shutting down gracefully');
  process.exit(0);
});

module.exports = { ClaudeAIMCPServer };