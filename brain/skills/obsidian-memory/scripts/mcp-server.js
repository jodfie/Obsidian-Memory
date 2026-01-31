#!/usr/bin/env node

/**
 * Obsidian-Memory HTTPS MCP Server
 * Provides semantic search and CRUD operations for Obsidian vault via HTTP/HTTPS
 */

const express = require('express');
const fs = require('fs').promises;
const path = require('path');
const cors = require('cors');
const crypto = require('crypto');

// Load environment variables from .env file
require('dotenv').config();

// Configuration
const PORT = process.env.PORT || 3001;
const VAULT_PATH = process.env.VAULT_PATH || '/home/redleif/Obsidian-Memory/brain';
const API_KEY = process.env.MCP_API_KEY || 'your-secret-api-key-here';

class ObsidianMemoryMCP {
  constructor(vaultPath) {
    this.vaultPath = vaultPath;
    this.memoryDir = path.join(vaultPath, 'memory');
    this.memoryFile = path.join(vaultPath, 'MEMORY.md');
  }

  // Authentication middleware
  authenticate(req, res, next) {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Missing or invalid authorization header' });
    }
    
    const token = authHeader.split(' ')[1];
    if (token !== API_KEY) {
      return res.status(401).json({ error: 'Invalid API key' });
    }
    
    next();
  }

  // Get current date in YYYY-MM-DD format
  getCurrentDate() {
    return new Date().toISOString().split('T')[0];
  }

  // Search memory files (simple text search for now)
  async searchMemory(query, maxResults = 10) {
    const results = [];
    
    try {
      // Search MEMORY.md
      try {
        const memoryContent = await fs.readFile(this.memoryFile, 'utf8');
        const lines = memoryContent.split('\n');
        const matches = lines
          .map((line, index) => ({ line, index: index + 1, file: 'MEMORY.md' }))
          .filter(({ line }) => line.toLowerCase().includes(query.toLowerCase()));
        
        results.push(...matches.slice(0, Math.floor(maxResults / 2)));
      } catch (err) {
        console.warn('Could not read MEMORY.md:', err.message);
      }

      // Search daily files
      try {
        const files = await fs.readdir(this.memoryDir);
        const mdFiles = files.filter(f => f.endsWith('.md')).sort().reverse();
        
        for (const file of mdFiles.slice(0, 10)) { // Last 10 days
          try {
            const content = await fs.readFile(path.join(this.memoryDir, file), 'utf8');
            const lines = content.split('\n');
            const matches = lines
              .map((line, index) => ({ line, index: index + 1, file: `memory/${file}` }))
              .filter(({ line }) => line.toLowerCase().includes(query.toLowerCase()));
            
            results.push(...matches.slice(0, 2));
            if (results.length >= maxResults) break;
          } catch (err) {
            console.warn(`Could not read ${file}:`, err.message);
          }
        }
      } catch (err) {
        console.warn('Could not read memory directory:', err.message);
      }

      return results.slice(0, maxResults);
    } catch (error) {
      throw new Error(`Search failed: ${error.message}`);
    }
  }

  // Get content from memory file
  async getMemory(filePath, startLine = null, numLines = null) {
    try {
      const fullPath = filePath.startsWith('/') 
        ? filePath 
        : path.join(this.vaultPath, filePath);
      
      const content = await fs.readFile(fullPath, 'utf8');
      
      if (startLine !== null) {
        const lines = content.split('\n');
        const start = Math.max(0, startLine - 1);
        const end = numLines ? start + numLines : lines.length;
        return {
          content: lines.slice(start, end).join('\n'),
          lines: end - start,
          totalLines: lines.length
        };
      }
      
      return { content, lines: content.split('\n').length };
    } catch (error) {
      throw new Error(`Failed to read ${filePath}: ${error.message}`);
    }
  }

  // Write to memory file
  async writeMemory(filePath, content, append = false) {
    try {
      const fullPath = filePath.startsWith('/') 
        ? filePath 
        : path.join(this.vaultPath, filePath);
      
      // Ensure directory exists
      await fs.mkdir(path.dirname(fullPath), { recursive: true });
      
      if (append) {
        await fs.appendFile(fullPath, '\n' + content);
      } else {
        await fs.writeFile(fullPath, content, 'utf8');
      }
      
      return { success: true, path: filePath };
    } catch (error) {
      throw new Error(`Failed to write ${filePath}: ${error.message}`);
    }
  }

  // Log to today's memory file
  async logMemory(content, category = null) {
    const today = this.getCurrentDate();
    const todayFile = path.join(this.memoryDir, `${today}.md`);
    
    try {
      // Check if file exists
      let existingContent = '';
      try {
        existingContent = await fs.readFile(todayFile, 'utf8');
      } catch (err) {
        // File doesn't exist, create header
        existingContent = `# ${today} Memory Log\n\n`;
      }
      
      const timestamp = new Date().toLocaleTimeString('en-US', { 
        timeZone: 'America/New_York',
        hour12: false 
      });
      
      const entry = category 
        ? `## ${category} (${timestamp})\n\n${content}\n\n`
        : `### ${timestamp}\n\n${content}\n\n`;
      
      await fs.writeFile(todayFile, existingContent + entry, 'utf8');
      
      return { success: true, file: `memory/${today}.md` };
    } catch (error) {
      throw new Error(`Failed to log memory: ${error.message}`);
    }
  }
}

// Initialize server
const app = express();
const memoryMCP = new ObsidianMemoryMCP(VAULT_PATH);

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// MCP Protocol Implementation
app.post('/mcp', memoryMCP.authenticate.bind(memoryMCP), async (req, res) => {
  try {
    const { method, params = {} } = req.body;
    
    switch (method) {
      case 'memory_search':
        const searchResults = await memoryMCP.searchMemory(
          params.query, 
          params.maxResults || 10
        );
        return res.json({
          results: searchResults.map(r => ({
            path: r.file,
            line: r.index,
            content: r.line.trim(),
            score: r.line.toLowerCase().includes(params.query.toLowerCase()) ? 0.8 : 0.5
          }))
        });

      case 'memory_get':
        const memoryContent = await memoryMCP.getMemory(
          params.path,
          params.from,
          params.lines
        );
        return res.json(memoryContent);

      case 'memory_write':
        const writeResult = await memoryMCP.writeMemory(
          params.path,
          params.content,
          params.append
        );
        return res.json(writeResult);

      case 'memory_log':
        const logResult = await memoryMCP.logMemory(
          params.content,
          params.category
        );
        return res.json(logResult);

      case 'list_tools':
        return res.json({
          tools: [
            {
              name: 'memory_search',
              description: 'Search memory files for content',
              inputSchema: {
                type: 'object',
                properties: {
                  query: { type: 'string', description: 'Search query' },
                  maxResults: { type: 'number', description: 'Max results to return' }
                },
                required: ['query']
              }
            },
            {
              name: 'memory_get',
              description: 'Get content from a memory file',
              inputSchema: {
                type: 'object',
                properties: {
                  path: { type: 'string', description: 'File path relative to vault' },
                  from: { type: 'number', description: 'Starting line number' },
                  lines: { type: 'number', description: 'Number of lines to read' }
                },
                required: ['path']
              }
            },
            {
              name: 'memory_write',
              description: 'Write content to a memory file',
              inputSchema: {
                type: 'object',
                properties: {
                  path: { type: 'string', description: 'File path relative to vault' },
                  content: { type: 'string', description: 'Content to write' },
                  append: { type: 'boolean', description: 'Append instead of overwrite' }
                },
                required: ['path', 'content']
              }
            },
            {
              name: 'memory_log',
              description: 'Log entry to today\'s memory file',
              inputSchema: {
                type: 'object',
                properties: {
                  content: { type: 'string', description: 'Content to log' },
                  category: { type: 'string', description: 'Optional category' }
                },
                required: ['content']
              }
            }
          ]
        });

      default:
        return res.status(400).json({ error: `Unknown method: ${method}` });
    }
  } catch (error) {
    console.error('MCP Error:', error);
    return res.status(500).json({ error: error.message });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    vault: VAULT_PATH,
    timestamp: new Date().toISOString()
  });
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🧠 Obsidian-Memory MCP Server running on port ${PORT}`);
  console.log(`📁 Vault path: ${VAULT_PATH}`);
  console.log(`🔑 Authentication: ${API_KEY === 'your-secret-api-key-here' ? '⚠️  Default API key' : '✅ Custom API key'}`);
});

module.exports = { ObsidianMemoryMCP };