---
name: obsidian-memory-web
description: Connect Claude.ai (web) to Obsidian-Memory MCP server via Streamable HTTP. Provides 16 tools for knowledge management, search, graph traversal, session tracking, and recall. No local installation required.
---

# Obsidian-Memory for Claude.ai (Web)

Integration skill for connecting **Claude.ai** (web interface) to the Obsidian-Memory MCP server using Streamable HTTP transport.

## Quick Setup

### Step 1: Open MCP Settings

1. Go to [claude.ai](https://claude.ai)
2. Click your profile icon (bottom-left)
3. Select **Settings**
4. Navigate to **Integrations** (or **MCP Servers**)

### Step 2: Add MCP Server

1. Click **"Add Integration"** or **"Add MCP Server"**
2. Enter the following:
   - **Name**: `Obsidian-Memory`
   - **URL**: `https://memory.example.com/mcp`
3. Click **Save** / **Add**

### Step 3: Authentication

If your deployment requires authentication:
- The server accepts a Bearer token via the `Authorization` header
- Configure the API key in the MCP server settings when prompted
- Contact your admin for the API key if using a shared deployment

### Step 4: Verify

Start a new conversation and ask Claude to use one of the memory tools:

> "Use mem_search to find notes about authentication"

Claude should invoke the tool and return results from your knowledge base.

## No Local Installation Required

Unlike Claude Code and Claude Desktop, the web interface connects directly to the remote MCP endpoint over HTTPS. You only need:

- A running Obsidian-Memory deployment (e.g., `memory.example.com`)
- The MCP endpoint URL
- An API key (if auth is enabled)

## Session Tracking

Unlike Claude Code (which has automatic session tracking via hooks), Claude.ai web requires **manual session tracking** using the MCP session tools:

- `session_observe` — log events during a conversation
- `session_summary` — generate AI summary when done
- `session_context` — retrieve past session context

For automatic tracking, use the [Claude Code skill](../obsidian-memory-code/SKILL.md) which includes 10 hooks that capture prompts, file edits, searches, and more with zero token cost.

## Usage in Conversations

Once connected, you can use natural language to interact with your knowledge base:

### Search & Discovery
- "Search my notes for Docker deployment patterns"
- "Find all notes tagged with 'security'"
- "What knowledge do I have about API design?"

### Reading & Context
- "Read the note about database migrations"
- "Build context from my authentication-related notes"
- "Get my project profile for the TechKB project"

### Writing & Logging
- "Save this solution as a knowledge note titled 'Redis Caching Pattern'"
- "Log this decision: chose PostgreSQL over MySQL for ACID compliance"
- "Create a session observation about the deployment issue we fixed"

### Graph Exploration
- "Find notes similar to my API gateway documentation"
- "Traverse the knowledge graph starting from note 42"
- "What notes are connected to my infrastructure docs?"

### Recall
- "Recall what I know about Cloudflare Workers"
- "What's my profile for the Brain project?"

## MCP Tools Reference

### Memory Operations

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `mem_read` | Read a note by ID, permalink, or query | `id`, `permalink`, `query`, `vault` |
| `mem_write` | Create or update a note | `title`\*, `content`\*, `relative_path`\*, `note_type`, `project`, `tags` |
| `mem_search` | Full-text search with filters | `query`\*, `vault`, `project`, `note_type`, `tags`, `sort`, `limit` |
| `mem_delete` | Permanently delete a note | `id`\* |
| `mem_supersede` | Mark note as replaced by another | `old_note_id`\*, `new_note_id`\*, `reason` |

### Context & Graph

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `build_context` | Build context from memory:// URIs | `uris`\* (array) |
| `graph_traverse` | Traverse knowledge graph (BFS/DFS) | `start_node_id`\*, `method`, `max_depth`, `direction` |
| `graph_similar` | Find similar notes | `note_id`\*, `limit`, `method` |

### Projects

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `project_list` | List all projects with note counts | `response_format` |
| `project_switch` | Switch to project context | `project_name`\* |
| `project_create` | Create a new project | `project_name`\* |

### Sessions

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `session_observe` | Log an event to a session | `session_id`\*, `event_type`\*, `content`\* |
| `session_summary` | Generate AI summary of a session | `session_id`\* |
| `session_context` | Get session events and summary | `session_id`\* |

### Profile & Recall

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `get_profile` | Get user/project profile | `project`\* |
| `recall` | Search memories + profile summary | `query`\* |

\* = required parameter

### Note Types

`note` | `decision` | `error` | `knowledge` | `pattern` | `session` | `research`

### memory:// URI Patterns (for `build_context`)

```
memory://note/123          — Note by ID
memory://search/auth       — Search for "auth"
memory://tags/security     — Notes tagged "security"
memory://project/api       — Notes in project "api"
```

### Response Formats

Most tools accept `response_format`: `"json"` (default, structured) or `"markdown"` (human-readable).

## Troubleshooting

**"Integration not connected" or tools not appearing:**
- Verify the MCP URL is correct and accessible (open in browser — should return a valid response)
- Check your API key if authentication is required
- Try removing and re-adding the integration
- Refresh the page and start a new conversation

**Tools return errors:**
- Verify the backend is running: visit `https://memory.example.com/api/health`
- Check if the Docker containers are healthy: `docker ps | grep memory`
- API key may have expired — regenerate and update in settings

**Slow responses:**
- Streamable HTTP adds network latency vs. local stdio
- Large search results may take longer — use `limit` parameter to constrain results
- Check server load if self-hosted

## Architecture

```
Claude.ai (Web Browser)
    |
    | Streamable HTTP (HTTPS)
    v
MCP Server (memory-mcp container, port 3000)
    |
    | HTTP (Docker internal network)
    v
Backend API (memory container, port 8765)
    |
    v
SQLite DB + Markdown Vault Files
```

The MCP server (`mcp-server/`) acts as a protocol bridge between Claude.ai's MCP client and the backend REST API. It translates MCP tool calls into REST API requests and formats responses back as MCP tool results.
