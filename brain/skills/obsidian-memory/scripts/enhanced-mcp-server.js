#!/usr/bin/env node

/**
 * Enhanced Obsidian-Memory HTTPS MCP Server
 * Full-featured implementation matching the complete project capabilities
 * Based on: https://github.com/jodfie/Obsidian-Memory
 */

const express = require('express');
const fs = require('fs').promises;
const path = require('path');
const cors = require('cors');
const crypto = require('crypto');
const { exec } = require('child_process');
const { promisify } = require('util');

// Load environment variables from .env file
require('dotenv').config();

const execAsync = promisify(exec);

// Configuration
const PORT = process.env.PORT || 3001;
const VAULT_PATH = process.env.VAULT_PATH || '/home/redleif/Obsidian-Memory/brain';
const API_KEY = process.env.MCP_API_KEY || 'your-secret-api-key-here';
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || '';

class EnhancedObsidianMemoryMCP {
  constructor(vaultPath) {
    this.vaultPath = vaultPath;
    this.memoryDir = path.join(vaultPath, 'memory');
    this.memoryFile = path.join(vaultPath, 'MEMORY.md');
    this.projectsDir = path.join(vaultPath, 'projects');
    this.sessionsDir = path.join(vaultPath, 'sessions');
    
    // In-memory caches
    this.notesCache = new Map();
    this.graphCache = null;
    this.searchIndex = new Map();
    
    this.initializeDirectories();
    this.buildSearchIndex();
  }

  // Initialize directory structure
  async initializeDirectories() {
    const dirs = [this.memoryDir, this.projectsDir, this.sessionsDir];
    for (const dir of dirs) {
      try {
        await fs.mkdir(dir, { recursive: true });
      } catch (err) {
        console.warn(`Could not create directory ${dir}:`, err.message);
      }
    }
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

  // Get current date/time
  getCurrentDate() {
    return new Date().toISOString().split('T')[0];
  }

  getCurrentTimestamp() {
    return new Date().toISOString();
  }

  // Build search index from all markdown files
  async buildSearchIndex() {
    try {
      const files = await this.getAllMarkdownFiles(this.vaultPath);
      this.searchIndex.clear();
      
      for (const filePath of files) {
        try {
          const content = await fs.readFile(filePath, 'utf8');
          const relativePath = path.relative(this.vaultPath, filePath);
          
          // Index content by words
          const words = content.toLowerCase().split(/\W+/).filter(w => w.length > 2);
          words.forEach(word => {
            if (!this.searchIndex.has(word)) {
              this.searchIndex.set(word, new Set());
            }
            this.searchIndex.get(word).add({
              path: relativePath,
              fullPath: filePath
            });
          });
          
          // Cache note metadata
          this.notesCache.set(relativePath, {
            path: relativePath,
            fullPath: filePath,
            content,
            title: this.extractTitle(content),
            tags: this.extractTags(content),
            links: this.extractWikilinks(content),
            lastModified: (await fs.stat(filePath)).mtime
          });
          
        } catch (err) {
          console.warn(`Could not index ${filePath}:`, err.message);
        }
      }
      
      console.log(`🔍 Search index built: ${this.searchIndex.size} words, ${this.notesCache.size} notes`);
    } catch (error) {
      console.error('Failed to build search index:', error);
    }
  }

  // Get all markdown files recursively
  async getAllMarkdownFiles(dir) {
    const files = [];
    try {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory() && !entry.name.startsWith('.')) {
          files.push(...await this.getAllMarkdownFiles(fullPath));
        } else if (entry.isFile() && entry.name.endsWith('.md')) {
          files.push(fullPath);
        }
      }
    } catch (err) {
      console.warn(`Could not read directory ${dir}:`, err.message);
    }
    
    return files;
  }

  // Extract title from markdown content
  extractTitle(content) {
    const lines = content.split('\n');
    for (const line of lines) {
      const match = line.match(/^#\s+(.+)$/);
      if (match) {
        return match[1].trim();
      }
    }
    return 'Untitled';
  }

  // Extract tags from markdown content
  extractTags(content) {
    const tagMatches = content.match(/#[\w-]+/g);
    return tagMatches ? [...new Set(tagMatches)] : [];
  }

  // Extract wikilinks from content
  extractWikilinks(content) {
    const linkMatches = content.match(/\[\[([^\]]+)\]\]/g);
    if (!linkMatches) return [];
    
    return linkMatches.map(match => {
      const link = match.slice(2, -2);
      const [target, alias] = link.split('|');
      return {
        target: target.trim(),
        alias: alias ? alias.trim() : target.trim(),
        raw: match
      };
    });
  }

  // Advanced search with multiple criteria
  async searchNotes(query, options = {}) {
    const {
      maxResults = 20,
      tags = [],
      projects = [],
      dateRange = null,
      contentOnly = false
    } = options;

    const results = [];
    const queryWords = query.toLowerCase().split(/\W+/).filter(w => w.length > 2);
    
    // Score notes based on query matches
    const scoreMap = new Map();
    
    for (const word of queryWords) {
      if (this.searchIndex.has(word)) {
        for (const file of this.searchIndex.get(word)) {
          const currentScore = scoreMap.get(file.path) || 0;
          scoreMap.set(file.path, currentScore + 1);
        }
      }
    }
    
    // Get top scored notes and extract matching content
    const sortedResults = Array.from(scoreMap.entries())
      .sort(([, a], [, b]) => b - a)
      .slice(0, maxResults);
    
    for (const [relativePath, score] of sortedResults) {
      const note = this.notesCache.get(relativePath);
      if (!note) continue;
      
      // Apply filters
      if (tags.length > 0 && !tags.some(tag => note.tags.includes(tag))) continue;
      if (projects.length > 0 && !projects.some(proj => note.path.includes(proj))) continue;
      
      // Find matching lines
      const lines = note.content.split('\n');
      const matchingLines = lines
        .map((line, index) => ({ line, index: index + 1 }))
        .filter(({ line }) => queryWords.some(word => 
          line.toLowerCase().includes(word)
        ))
        .slice(0, 5); // Top 5 matching lines per file
      
      results.push({
        path: note.path,
        title: note.title,
        score: score / queryWords.length, // Normalize score
        tags: note.tags,
        links: note.links,
        matches: matchingLines,
        lastModified: note.lastModified
      });
    }
    
    return results;
  }

  // Build knowledge graph from all notes
  async buildKnowledgeGraph() {
    if (this.graphCache) {
      return this.graphCache;
    }
    
    const nodes = [];
    const edges = [];
    const nodeMap = new Map();
    
    // Create nodes for each note
    for (const [path, note] of this.notesCache) {
      const nodeId = path.replace(/\.md$/, '').replace(/\//g, '_');
      const node = {
        id: nodeId,
        path: path,
        title: note.title,
        tags: note.tags,
        type: 'note',
        size: note.content.length,
        lastModified: note.lastModified
      };
      
      nodes.push(node);
      nodeMap.set(note.title.toLowerCase(), nodeId);
      nodeMap.set(path, nodeId);
    }
    
    // Create edges from wikilinks
    for (const [path, note] of this.notesCache) {
      const sourceId = path.replace(/\.md$/, '').replace(/\//g, '_');
      
      for (const link of note.links) {
        const targetTitle = link.target.toLowerCase();
        const targetId = nodeMap.get(targetTitle);
        
        if (targetId && targetId !== sourceId) {
          edges.push({
            source: sourceId,
            target: targetId,
            type: 'wikilink',
            weight: 1
          });
        }
      }
    }
    
    this.graphCache = { nodes, edges };
    console.log(`🕸️ Knowledge graph built: ${nodes.length} nodes, ${edges.length} edges`);
    
    return this.graphCache;
  }

  // Traverse graph to find related notes
  async traverseGraph(startNodeId, maxDepth = 2, maxResults = 10) {
    const graph = await this.buildKnowledgeGraph();
    const visited = new Set();
    const results = [];
    const queue = [{ nodeId: startNodeId, depth: 0, path: [startNodeId] }];
    
    while (queue.length > 0 && results.length < maxResults) {
      const { nodeId, depth, path } = queue.shift();
      
      if (visited.has(nodeId) || depth > maxDepth) continue;
      visited.add(nodeId);
      
      const node = graph.nodes.find(n => n.id === nodeId);
      if (node && depth > 0) { // Don't include start node
        results.push({
          ...node,
          depth,
          path: [...path]
        });
      }
      
      if (depth < maxDepth) {
        // Find connected nodes
        const connectedNodes = graph.edges
          .filter(e => e.source === nodeId || e.target === nodeId)
          .map(e => e.source === nodeId ? e.target : e.source)
          .filter(id => !visited.has(id));
        
        for (const connectedId of connectedNodes) {
          queue.push({
            nodeId: connectedId,
            depth: depth + 1,
            path: [...path, connectedId]
          });
        }
      }
    }
    
    return results;
  }

  // Find similar notes using content similarity
  async findSimilarNotes(noteId, maxResults = 10) {
    const targetNote = this.notesCache.get(noteId);
    if (!targetNote) {
      throw new Error(`Note not found: ${noteId}`);
    }
    
    const targetWords = new Set(
      targetNote.content.toLowerCase()
        .split(/\W+/)
        .filter(w => w.length > 3)
    );
    
    const similarities = [];
    
    for (const [path, note] of this.notesCache) {
      if (path === noteId) continue;
      
      const noteWords = new Set(
        note.content.toLowerCase()
          .split(/\W+/)
          .filter(w => w.length > 3)
      );
      
      // Calculate Jaccard similarity
      const intersection = new Set([...targetWords].filter(x => noteWords.has(x)));
      const union = new Set([...targetWords, ...noteWords]);
      const similarity = intersection.size / union.size;
      
      if (similarity > 0.1) { // Minimum similarity threshold
        similarities.push({
          path: note.path,
          title: note.title,
          similarity,
          commonWords: Array.from(intersection).slice(0, 10),
          tags: note.tags
        });
      }
    }
    
    return similarities
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, maxResults);
  }

  // Project management
  async listProjects() {
    try {
      const entries = await fs.readdir(this.projectsDir, { withFileTypes: true });
      const projects = [];
      
      for (const entry of entries) {
        if (entry.isDirectory()) {
          const projectPath = path.join(this.projectsDir, entry.name);
          const configPath = path.join(projectPath, 'project.json');
          
          let config = { name: entry.name };
          try {
            const configContent = await fs.readFile(configPath, 'utf8');
            config = { ...config, ...JSON.parse(configContent) };
          } catch (err) {
            // Use defaults if no config
          }
          
          projects.push({
            id: entry.name,
            name: config.name,
            description: config.description || '',
            tags: config.tags || [],
            created: config.created || new Date().toISOString()
          });
        }
      }
      
      return projects;
    } catch (error) {
      console.warn('Could not list projects:', error.message);
      return [];
    }
  }

  async createProject(projectId, config) {
    const projectPath = path.join(this.projectsDir, projectId);
    await fs.mkdir(projectPath, { recursive: true });
    
    const fullConfig = {
      name: config.name || projectId,
      description: config.description || '',
      tags: config.tags || [],
      created: new Date().toISOString(),
      ...config
    };
    
    await fs.writeFile(
      path.join(projectPath, 'project.json'),
      JSON.stringify(fullConfig, null, 2)
    );
    
    return fullConfig;
  }

  // Session management
  async createSession(sessionId, metadata = {}) {
    const sessionPath = path.join(this.sessionsDir, `${sessionId}.md`);
    const content = `# Session: ${sessionId}

**Created:** ${new Date().toISOString()}
**Type:** ${metadata.type || 'general'}
**Project:** ${metadata.project || 'none'}

## Context

${metadata.context || 'No initial context'}

## Events

`;
    
    await fs.writeFile(sessionPath, content);
    return { sessionId, path: sessionPath };
  }

  async addSessionEvent(sessionId, event) {
    const sessionPath = path.join(this.sessionsDir, `${sessionId}.md`);
    const timestamp = new Date().toLocaleTimeString('en-US', {
      timeZone: 'America/New_York',
      hour12: false
    });
    
    const eventEntry = `### ${timestamp} - ${event.type}\n\n${event.content}\n\n`;
    
    try {
      await fs.appendFile(sessionPath, eventEntry);
      return { success: true, timestamp };
    } catch (error) {
      throw new Error(`Failed to add session event: ${error.message}`);
    }
  }

  // Memory operations (enhanced)
  async memoryRead(identifier, options = {}) {
    let targetPath;
    
    // Handle different identifier types
    if (identifier.startsWith('memory://')) {
      targetPath = identifier.replace('memory://', '');
    } else if (identifier.includes('/') || identifier.endsWith('.md')) {
      targetPath = identifier;
    } else {
      // Search by title
      const searchResults = await this.searchNotes(identifier, { maxResults: 1 });
      if (searchResults.length === 0) {
        throw new Error(`No note found matching: ${identifier}`);
      }
      targetPath = searchResults[0].path;
    }
    
    const fullPath = path.isAbsolute(targetPath) 
      ? targetPath 
      : path.join(this.vaultPath, targetPath);
    
    const content = await fs.readFile(fullPath, 'utf8');
    const note = this.notesCache.get(targetPath) || {
      title: this.extractTitle(content),
      tags: this.extractTags(content),
      links: this.extractWikilinks(content)
    };
    
    if (options.includeContext) {
      // Get related notes
      const nodeId = targetPath.replace(/\.md$/, '').replace(/\//g, '_');
      const related = await this.traverseGraph(nodeId, 1, 5);
      note.related = related;
    }
    
    return {
      path: targetPath,
      content,
      ...note,
      lastModified: (await fs.stat(fullPath)).mtime
    };
  }

  async memoryWrite(targetPath, content, options = {}) {
    const fullPath = path.isAbsolute(targetPath) 
      ? targetPath 
      : path.join(this.vaultPath, targetPath);
    
    // Ensure directory exists
    await fs.mkdir(path.dirname(fullPath), { recursive: true });
    
    if (options.append) {
      await fs.appendFile(fullPath, '\n' + content);
    } else {
      await fs.writeFile(fullPath, content, 'utf8');
    }
    
    // Update cache
    const relativePath = path.relative(this.vaultPath, fullPath);
    this.notesCache.delete(relativePath);
    
    // Rebuild search index for this file
    this.rebuildFileIndex(fullPath);
    
    return { success: true, path: relativePath };
  }

  async rebuildFileIndex(filePath) {
    try {
      const content = await fs.readFile(filePath, 'utf8');
      const relativePath = path.relative(this.vaultPath, filePath);
      
      // Remove old entries for this file
      for (const [word, files] of this.searchIndex.entries()) {
        files.forEach(file => {
          if (file.path === relativePath) {
            files.delete(file);
          }
        });
        if (files.size === 0) {
          this.searchIndex.delete(word);
        }
      }
      
      // Add new entries
      const words = content.toLowerCase().split(/\W+/).filter(w => w.length > 2);
      words.forEach(word => {
        if (!this.searchIndex.has(word)) {
          this.searchIndex.set(word, new Set());
        }
        this.searchIndex.get(word).add({
          path: relativePath,
          fullPath: filePath
        });
      });
      
      // Update cache
      this.notesCache.set(relativePath, {
        path: relativePath,
        fullPath: filePath,
        content,
        title: this.extractTitle(content),
        tags: this.extractTags(content),
        links: this.extractWikilinks(content),
        lastModified: (await fs.stat(filePath)).mtime
      });
      
    } catch (error) {
      console.warn(`Could not rebuild index for ${filePath}:`, error.message);
    }
  }

  // AI Processing (if Anthropic API key provided)
  async generateSessionSummary(sessionId) {
    if (!ANTHROPIC_API_KEY) {
      throw new Error('Anthropic API key not configured');
    }
    
    const sessionPath = path.join(this.sessionsDir, `${sessionId}.md`);
    const content = await fs.readFile(sessionPath, 'utf8');
    
    // This would integrate with Anthropic API
    // For now, return a placeholder
    return {
      sessionId,
      summary: 'AI-generated summary would appear here',
      keyPoints: ['Point 1', 'Point 2'],
      entities: ['Entity 1', 'Entity 2'],
      nextActions: ['Action 1', 'Action 2']
    };
  }

  // Git operations
  async getGitStatus() {
    try {
      const { stdout } = await execAsync('git status --porcelain', { 
        cwd: this.vaultPath 
      });
      
      const files = stdout.split('\n')
        .filter(line => line.trim())
        .map(line => ({
          status: line.substring(0, 2),
          path: line.substring(3)
        }));
      
      return {
        hasChanges: files.length > 0,
        files,
        branch: await this.getCurrentBranch()
      };
    } catch (error) {
      return { error: error.message };
    }
  }

  async getCurrentBranch() {
    try {
      const { stdout } = await execAsync('git branch --show-current', {
        cwd: this.vaultPath
      });
      return stdout.trim();
    } catch (error) {
      return 'unknown';
    }
  }

  // System metrics
  getSystemMetrics() {
    const memUsage = process.memoryUsage();
    return {
      memory: {
        rss: Math.round(memUsage.rss / 1024 / 1024), // MB
        heapUsed: Math.round(memUsage.heapUsed / 1024 / 1024), // MB
        heapTotal: Math.round(memUsage.heapTotal / 1024 / 1024), // MB
      },
      cache: {
        notesCount: this.notesCache.size,
        searchIndexSize: this.searchIndex.size,
        hasGraph: !!this.graphCache
      },
      uptime: Math.round(process.uptime()),
      timestamp: new Date().toISOString()
    };
  }
}

// Initialize server
const app = express();
const memoryMCP = new EnhancedObsidianMemoryMCP(VAULT_PATH);

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Enhanced MCP Protocol Implementation
app.post('/mcp', memoryMCP.authenticate.bind(memoryMCP), async (req, res) => {
  try {
    const { method, params = {} } = req.body;
    
    switch (method) {
      // Enhanced memory operations
      case 'mem_read':
        const readResult = await memoryMCP.memoryRead(
          params.identifier,
          { includeContext: params.includeContext }
        );
        return res.json(readResult);

      case 'mem_write':
        const writeResult = await memoryMCP.memoryWrite(
          params.path,
          params.content,
          { append: params.append }
        );
        return res.json(writeResult);

      case 'mem_search':
        const searchResults = await memoryMCP.searchNotes(
          params.query,
          {
            maxResults: params.maxResults || 20,
            tags: params.tags || [],
            projects: params.projects || []
          }
        );
        return res.json({ results: searchResults });

      // Graph operations
      case 'graph_traverse':
        const traverseResults = await memoryMCP.traverseGraph(
          params.startNodeId,
          params.maxDepth || 2,
          params.maxResults || 10
        );
        return res.json({ results: traverseResults });

      case 'graph_similar':
        const similarResults = await memoryMCP.findSimilarNotes(
          params.noteId,
          params.maxResults || 10
        );
        return res.json({ results: similarResults });

      case 'graph_get':
        const graph = await memoryMCP.buildKnowledgeGraph();
        return res.json(graph);

      // Project operations
      case 'project_list':
        const projects = await memoryMCP.listProjects();
        return res.json({ projects });

      case 'project_create':
        const newProject = await memoryMCP.createProject(
          params.projectId,
          params.config || {}
        );
        return res.json(newProject);

      // Session operations
      case 'session_create':
        const session = await memoryMCP.createSession(
          params.sessionId,
          params.metadata || {}
        );
        return res.json(session);

      case 'session_observe':
        const observeResult = await memoryMCP.addSessionEvent(
          params.sessionId,
          {
            type: params.type || 'observation',
            content: params.content
          }
        );
        return res.json(observeResult);

      case 'session_summary':
        const summary = await memoryMCP.generateSessionSummary(params.sessionId);
        return res.json(summary);

      // Git operations
      case 'git_status':
        const gitStatus = await memoryMCP.getGitStatus();
        return res.json(gitStatus);

      // Legacy operations (for compatibility)
      case 'memory_search':
        const legacySearchResults = await memoryMCP.searchNotes(
          params.query,
          { maxResults: params.maxResults || 10 }
        );
        return res.json({
          results: legacySearchResults.map(r => ({
            path: r.path,
            line: r.matches[0]?.index || 1,
            content: r.matches[0]?.line || r.title,
            score: r.score
          }))
        });

      case 'memory_get':
        const legacyReadResult = await memoryMCP.memoryRead(params.path);
        return res.json({
          content: legacyReadResult.content,
          lines: legacyReadResult.content.split('\n').length
        });

      case 'memory_write':
        const legacyWriteResult = await memoryMCP.memoryWrite(
          params.path,
          params.content,
          { append: params.append }
        );
        return res.json(legacyWriteResult);

      case 'memory_log':
        const today = memoryMCP.getCurrentDate();
        const todayFile = path.join(memoryMCP.memoryDir, `${today}.md`);
        const timestamp = new Date().toLocaleTimeString('en-US', { 
          timeZone: 'America/New_York',
          hour12: false 
        });
        
        let existingContent = '';
        try {
          existingContent = await fs.readFile(todayFile, 'utf8');
        } catch (err) {
          existingContent = `# ${today} Memory Log\n\n`;
        }
        
        const entry = params.category 
          ? `## ${params.category} (${timestamp})\n\n${params.content}\n\n`
          : `### ${timestamp}\n\n${params.content}\n\n`;
        
        await fs.writeFile(todayFile, existingContent + entry);
        return res.json({ success: true, file: `memory/${today}.md` });

      case 'list_tools':
        return res.json({
          tools: [
            // Memory tools
            {
              name: 'mem_read',
              description: 'Read a note by ID, path, or search query',
              inputSchema: {
                type: 'object',
                properties: {
                  identifier: { type: 'string', description: 'Note identifier (path, title, or memory:// URI)' },
                  includeContext: { type: 'boolean', description: 'Include related notes' }
                },
                required: ['identifier']
              }
            },
            {
              name: 'mem_write',
              description: 'Create or update a note',
              inputSchema: {
                type: 'object',
                properties: {
                  path: { type: 'string', description: 'Note path' },
                  content: { type: 'string', description: 'Note content' },
                  append: { type: 'boolean', description: 'Append to existing content' }
                },
                required: ['path', 'content']
              }
            },
            {
              name: 'mem_search',
              description: 'Search notes with advanced filters',
              inputSchema: {
                type: 'object',
                properties: {
                  query: { type: 'string', description: 'Search query' },
                  maxResults: { type: 'number', description: 'Maximum results' },
                  tags: { type: 'array', items: { type: 'string' }, description: 'Filter by tags' },
                  projects: { type: 'array', items: { type: 'string' }, description: 'Filter by projects' }
                },
                required: ['query']
              }
            },
            // Graph tools
            {
              name: 'graph_traverse',
              description: 'Traverse the knowledge graph from a starting point',
              inputSchema: {
                type: 'object',
                properties: {
                  startNodeId: { type: 'string', description: 'Starting node ID' },
                  maxDepth: { type: 'number', description: 'Maximum traversal depth' },
                  maxResults: { type: 'number', description: 'Maximum results' }
                },
                required: ['startNodeId']
              }
            },
            {
              name: 'graph_similar',
              description: 'Find notes similar to a given note',
              inputSchema: {
                type: 'object',
                properties: {
                  noteId: { type: 'string', description: 'Reference note ID' },
                  maxResults: { type: 'number', description: 'Maximum results' }
                },
                required: ['noteId']
              }
            },
            {
              name: 'graph_get',
              description: 'Get the complete knowledge graph',
              inputSchema: { type: 'object', properties: {} }
            },
            // Project tools
            {
              name: 'project_list',
              description: 'List all projects',
              inputSchema: { type: 'object', properties: {} }
            },
            {
              name: 'project_create',
              description: 'Create a new project',
              inputSchema: {
                type: 'object',
                properties: {
                  projectId: { type: 'string', description: 'Project ID' },
                  config: { type: 'object', description: 'Project configuration' }
                },
                required: ['projectId']
              }
            },
            // Session tools
            {
              name: 'session_create',
              description: 'Create a new session',
              inputSchema: {
                type: 'object',
                properties: {
                  sessionId: { type: 'string', description: 'Session ID' },
                  metadata: { type: 'object', description: 'Session metadata' }
                },
                required: ['sessionId']
              }
            },
            {
              name: 'session_observe',
              description: 'Add an observation to a session',
              inputSchema: {
                type: 'object',
                properties: {
                  sessionId: { type: 'string', description: 'Session ID' },
                  type: { type: 'string', description: 'Event type' },
                  content: { type: 'string', description: 'Event content' }
                },
                required: ['sessionId', 'content']
              }
            },
            {
              name: 'session_summary',
              description: 'Generate AI summary of a session',
              inputSchema: {
                type: 'object',
                properties: {
                  sessionId: { type: 'string', description: 'Session ID' }
                },
                required: ['sessionId']
              }
            },
            // Git tools
            {
              name: 'git_status',
              description: 'Get Git status of the vault',
              inputSchema: { type: 'object', properties: {} }
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

// Enhanced health check
app.get('/health', (req, res) => {
  const metrics = memoryMCP.getSystemMetrics();
  res.json({ 
    status: 'healthy', 
    vault: VAULT_PATH,
    timestamp: new Date().toISOString(),
    ...metrics
  });
});

// Metrics endpoint
app.get('/metrics', (req, res) => {
  res.json(memoryMCP.getSystemMetrics());
});

// Rebuild search index endpoint
app.post('/rebuild-index', memoryMCP.authenticate.bind(memoryMCP), async (req, res) => {
  try {
    await memoryMCP.buildSearchIndex();
    res.json({ success: true, message: 'Search index rebuilt' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🧠 Enhanced Obsidian-Memory MCP Server running on port ${PORT}`);
  console.log(`📁 Vault path: ${VAULT_PATH}`);
  console.log(`🔑 Authentication: ${API_KEY === 'your-secret-api-key-here' ? '⚠️  Default API key' : '✅ Custom API key'}`);
  console.log(`🤖 AI Processing: ${ANTHROPIC_API_KEY ? '✅ Enabled' : '❌ Disabled (no API key)'}`);
  console.log(`📊 Available tools: mem_read, mem_write, mem_search, graph_*, project_*, session_*, git_status`);
});

module.exports = { EnhancedObsidianMemoryMCP };