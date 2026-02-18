---
name: obsidian-memory-desktop
description: Connect Claude Desktop to Obsidian-Memory MCP server. Supports both stdio (local) and Streamable HTTP (remote) transports. Provides 16 tools for knowledge management, search, graph traversal, session tracking, and recall.
---

# Obsidian-Memory for Claude Desktop

Integration skill for connecting the **Claude Desktop** app to the Obsidian-Memory MCP server.

## Quick Setup

### Option A: Local stdio Transport (Recommended for Development)

Edit your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Add the `obsidian-memory` server:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "bun",
      "args": ["run", "src/index.ts"],
      "cwd": "/home/redleif/Obsidian-Memory/mcp-server",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OBSIDIAN_MEMORY_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Prerequisites for local setup:**
1. Install [bun](https://bun.sh): `curl -fsSL https://bun.sh/install | bash`
2. Clone the repo: `git clone https://github.com/jodfie/Obsidian-Memory`
3. Install deps: `cd Obsidian-Memory/mcp-server && bun install`
4. Ensure backend API is running (Docker or local)

### Option B: Remote Streamable HTTP Transport (Simpler)

If the Obsidian-Memory backend is deployed remotely (e.g., Docker on a server), connect directly via Streamable HTTP:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "url": "https://memory.redleif.dev/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

No local installation needed — just the URL and API key.

## Verification

After adding the config:

1. Restart Claude Desktop (Cmd+Q / Alt+F4, then reopen)
2. Open a new conversation
3. Click the MCP tools icon (hammer) in the input area
4. You should see 16 Obsidian-Memory tools listed

## Usage in Conversations

Once connected, Claude Desktop can use all 16 tools automatically. Example prompts:

- "Search my notes for authentication patterns"
- "What decisions have I made about the API architecture?"
- "Save this conversation summary to my knowledge base"
- "Find notes similar to my database design document"
- "What's the context from my last session?"

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
| `project_switch` | Switch to a project context | `project_name`\* |
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

## Troubleshooting

**Tools not appearing in Claude Desktop:**
- Verify the config file is valid JSON (use `jq . < config.json`)
- Restart Claude Desktop completely (not just close the window)
- Check `cwd` path exists and `bun` is in your PATH
- For remote: verify the URL is reachable in a browser

**Connection errors:**
- Local: ensure backend API is running (`curl http://localhost:8000/api/health`)
- Remote: check your API key is correct
- Remote: verify HTTPS certificate is valid

**Tools error during use:**
- Check if the backend database is accessible
- Restart Claude Desktop to reset MCP connections
- For Docker backend: `docker ps | grep memory` to verify container is running

## Architecture Notes

- **stdio transport**: Claude Desktop spawns the MCP server as a subprocess. Communication happens via stdin/stdout. Server exits when Desktop closes.
- **Streamable HTTP**: Claude Desktop connects to a remote MCP endpoint. No local process needed. Requires network access.
- The MCP server (`mcp-server/src/index.ts`) proxies requests to the backend REST API (`backend/`), which manages the SQLite database and markdown vault files.
