---
name: obsidian-memory
description: Connect to remote Obsidian-Memory HTTPS MCP server providing comprehensive knowledge management. Features: advanced search with filters, knowledge graph traversal, project management, session tracking, Git integration, and AI processing. Complete implementation of the full Obsidian-Memory project capabilities via HTTP API. Use for research, context building, knowledge discovery, and long-term memory management.
---

# Enhanced Obsidian-Memory MCP Server

Complete implementation of the **Obsidian-Memory project** (https://github.com/jodfie/Obsidian-Memory) as an HTTP MCP server, providing all capabilities of the full-featured knowledge management system.

## Features Overview

### 🔍 **Advanced Search & Discovery**
- **Full-text search** with SQLite-like indexing across all markdown files
- **Tag filtering** and **project-based filtering**  
- **Semantic similarity** detection between notes
- **Knowledge graph traversal** for related content discovery

### 🕸️ **Knowledge Graph**
- **Automatic graph construction** from wikilinks `[[note]]`
- **Node traversal** with configurable depth
- **Similarity detection** using content analysis
- **Visual relationship mapping** compatible with Obsidian graph view

### 📁 **Project Management** 
- **Multi-project organization** with dedicated folders
- **Project context switching** for focused work
- **Project-specific search** and filtering
- **Metadata management** with JSON configuration

### 📝 **Session Tracking**
- **Session creation** and **event logging**
- **Automatic timestamping** and categorization
- **AI-powered summarization** (with Anthropic API)
- **Context preservation** across sessions

### 🔄 **Git Integration**
- **Status monitoring** and **change tracking**
- **Branch awareness** for collaborative workflows
- **Sync state** reporting for cross-device work

### 🤖 **AI Processing** (Optional)
- **Entity extraction** and **relation inference**
- **Session summarization** with key insights
- **Content analysis** and **pattern detection**
- **Requires Anthropic API key**

## Quick Setup

### Enhanced Server Deployment

```bash
# On your server (redleif.dev)
cd skills/obsidian-memory/scripts/
./setup.sh     # Install dependencies  
./deploy.sh    # Deploy enhanced server to production

# Or use the enhanced server directly
node enhanced-mcp-server.js
```

### Configuration

Set these environment variables:

```bash
# Required
export OBSIDIAN_MEMORY_URL="https://memory.redleif.dev"
export OBSIDIAN_MEMORY_API_KEY="your-32-char-hex-key"

# Optional - AI features
export ANTHROPIC_API_KEY="your-anthropic-key"

# Optional - Custom vault path
export VAULT_PATH="/path/to/your/obsidian/vault"
```

## MCP Tools Available

### 📖 **Memory Operations**

#### Read Notes
```bash
# Read by path, title, or memory:// URI
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "mem_read",
    "params": {
      "identifier": "MEMORY.md",
      "includeContext": true
    }
  }'
```

#### Advanced Search
```bash
# Search with filters and advanced options
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "mem_search",
    "params": {
      "query": "browser automation",
      "maxResults": 10,
      "tags": ["#technical", "#automation"],
      "projects": ["web-testing"]
    }
  }'
```

#### Write & Update
```bash
# Create or update notes
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "mem_write",
    "params": {
      "path": "projects/new-project/notes.md",
      "content": "# Project Notes\n\n## Objectives\n...",
      "append": false
    }
  }'
```

### 🕸️ **Knowledge Graph Operations**

#### Traverse Connections
```bash
# Find related notes through wikilinks
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "graph_traverse",
    "params": {
      "startNodeId": "technical_notes",
      "maxDepth": 2,
      "maxResults": 10
    }
  }'
```

#### Find Similar Content
```bash
# Discover content similarity
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "graph_similar",
    "params": {
      "noteId": "memory/2024-01-27.md",
      "maxResults": 5
    }
  }'
```

#### Get Complete Graph
```bash
# Export full knowledge graph
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"method": "graph_get", "params": {}}'
```

### 📁 **Project Management**

#### List Projects
```bash
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"method": "project_list", "params": {}}'
```

#### Create Project
```bash
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "project_create",
    "params": {
      "projectId": "web-automation",
      "config": {
        "name": "Web Automation Project",
        "description": "Browser automation and testing",
        "tags": ["automation", "testing", "web"]
      }
    }
  }'
```

### 📝 **Session Tracking**

#### Create Session
```bash
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "session_create",
    "params": {
      "sessionId": "session-2024-01-27",
      "metadata": {
        "type": "development",
        "project": "obsidian-memory",
        "context": "Building MCP server functionality"
      }
    }
  }'
```

#### Add Session Events
```bash
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "session_observe",
    "params": {
      "sessionId": "session-2024-01-27",
      "type": "achievement",
      "content": "Successfully deployed enhanced MCP server with full capabilities"
    }
  }'
```

#### Generate AI Summary
```bash
# Requires ANTHROPIC_API_KEY
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "session_summary",
    "params": {
      "sessionId": "session-2024-01-27"
    }
  }'
```

### 🔄 **Git Integration**

#### Check Repository Status
```bash
curl -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
  -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"method": "git_status", "params": {}}'
```

## Helper Functions

For easier use in scripts, create wrapper functions:

```bash
# Add to ~/.bashrc or similar

memory_search() {
  local query="$1"
  local max_results="${2:-10}"
  
  curl -s -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
    -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"method\":\"memory_search\",\"params\":{\"query\":\"$query\",\"maxResults\":$max_results}}" \
    | jq -r '.results[] | "\(.path):\(.line) - \(.content)"'
}

memory_log() {
  local content="$1"
  local category="${2:-Notes}"
  
  curl -s -X POST "$OBSIDIAN_MEMORY_URL/mcp" \
    -H "Authorization: Bearer $OBSIDIAN_MEMORY_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"method\":\"memory_log\",\"params\":{\"content\":\"$content\",\"category\":\"$category\"}}"
}
```

## Usage Patterns

### Research & Discovery
```bash
# Find past solutions
memory_search "solved similar problem"

# Check previous decisions
memory_search "decided to use X because"
```

### Documentation
```bash
# Log important discoveries
memory_log "Found that X works better than Y for Z use case" "Technical"

# Update long-term memory
memory_write MEMORY.md "## New Insight\n\nX is better than Y because..." true
```

### Context Restoration
```bash
# Get recent context
memory_get "memory/$(date +%Y-%m-%d).md"

# Read long-term patterns
memory_get "MEMORY.md" 1 50
```

## Monitoring & Health

Check server health:
```bash
curl "$OBSIDIAN_MEMORY_URL/health"
```

View server logs:
```bash
# On the server
sudo journalctl -u obsidian-memory-mcp -f
```

## API Reference

See [references/api.md](references/api.md) for complete API documentation, including all methods, parameters, and response formats.

## Troubleshooting

**Connection refused**: Verify server is running and port is accessible
**401 Unauthorized**: Check API key configuration
**File not found**: Verify vault path and file exists
**500 Server Error**: Check server logs for detailed error information

The server runs as a systemd service on your target host, providing reliable HTTPS access to your Obsidian memory vault.