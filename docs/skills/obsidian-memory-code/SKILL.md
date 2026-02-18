---
name: obsidian-memory-code
description: Connect Claude Code to Obsidian-Memory MCP server via stdio transport. Provides 16 tools for knowledge management, search, graph traversal, session tracking, and recall. Includes config templates for user-level and project-level setup, permission allowlists, and CLAUDE.md integration patterns.
---

# Obsidian-Memory for Claude Code

Integration skill for connecting **Claude Code** (CLI) to the Obsidian-Memory MCP server using stdio transport.

## Quick Setup

### Option 1: Project-Level Config (`.mcp.json`)

Create `.mcp.json` in your project root:

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

### Option 2: User-Level Config (`~/.claude.json`)

Add to the `mcpServers` object in `~/.claude.json`:

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

### Option 3: Remote via Docker (No Local Install)

If the MCP server is running in Docker (e.g., `memory.redleif.dev`), point to the API URL:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "bun",
      "args": ["run", "src/index.ts"],
      "cwd": "/home/redleif/Obsidian-Memory/mcp-server",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OBSIDIAN_MEMORY_API_URL": "https://memory.redleif.dev/api"
      }
    }
  }
}
```

## Prerequisites

- **bun** (or Node.js 18+) installed
- Clone the Obsidian-Memory repo: `git clone https://github.com/jodfie/Obsidian-Memory`
- Install MCP server deps: `cd mcp-server && bun install`
- Backend API running (Docker or local)

## Permission Allowlist

Add to `.claude/settings.json` or `.claude/settings.local.json` to auto-approve tools:

```json
{
  "allowedTools": [
    "mcp__obsidian-memory__mem_read",
    "mcp__obsidian-memory__mem_search",
    "mcp__obsidian-memory__mem_write",
    "mcp__obsidian-memory__mem_delete",
    "mcp__obsidian-memory__mem_supersede",
    "mcp__obsidian-memory__build_context",
    "mcp__obsidian-memory__graph_traverse",
    "mcp__obsidian-memory__graph_similar",
    "mcp__obsidian-memory__project_list",
    "mcp__obsidian-memory__project_switch",
    "mcp__obsidian-memory__project_create",
    "mcp__obsidian-memory__session_observe",
    "mcp__obsidian-memory__session_summary",
    "mcp__obsidian-memory__session_context",
    "mcp__obsidian-memory__get_profile",
    "mcp__obsidian-memory__recall"
  ]
}
```

For a safer default, allow only read operations:

```json
{
  "allowedTools": [
    "mcp__obsidian-memory__mem_read",
    "mcp__obsidian-memory__mem_search",
    "mcp__obsidian-memory__build_context",
    "mcp__obsidian-memory__graph_traverse",
    "mcp__obsidian-memory__graph_similar",
    "mcp__obsidian-memory__project_list",
    "mcp__obsidian-memory__project_switch",
    "mcp__obsidian-memory__session_context",
    "mcp__obsidian-memory__get_profile",
    "mcp__obsidian-memory__recall"
  ]
}
```

## Verification

After configuring, verify the connection:

```
/mcp
```

You should see `obsidian-memory` listed with 16 tools connected.

## CLAUDE.md Integration

Add to your project's `CLAUDE.md` for automatic context:

```markdown
## Obsidian-Memory Integration

This project uses Obsidian-Memory for persistent knowledge management.

### Usage Patterns
- **Before starting work**: Use `recall` to check for relevant past context
- **Search first**: Use `mem_search` before answering questions about past decisions
- **Log decisions**: Use `mem_write` to record architectural decisions and patterns
- **Session tracking**: Use `session_observe` to log significant events
- **Build context**: Use `build_context` with memory:// URIs to gather related notes

### Memory-Aware Workflow
1. `recall` or `mem_search` for existing knowledge
2. Work on the task
3. `mem_write` important decisions/patterns/solutions
4. `session_observe` significant events
```

## MCP Tools Reference

### Memory Operations

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `mem_read` | Read a note by ID, permalink, or search query | `id`, `permalink`, `query`, `vault` |
| `mem_write` | Create or update a note | `title`\*, `content`\*, `relative_path`\*, `note_type`, `project`, `tags` |
| `mem_search` | Full-text search with filters (FTS5 syntax) | `query`\*, `vault`, `project`, `note_type`, `tags`, `sort`, `limit` |
| `mem_delete` | Permanently delete a note by ID | `id`\* |
| `mem_supersede` | Mark a note as replaced by another | `old_note_id`\*, `new_note_id`\*, `reason` |

### Context & Graph

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `build_context` | Build context from memory:// URI patterns | `uris`\* (array of memory:// URIs) |
| `graph_traverse` | Traverse knowledge graph (BFS/DFS) | `start_node_id`\*, `method`, `max_depth`, `direction` |
| `graph_similar` | Find similar notes by graph/content | `note_id`\*, `limit`, `method` (graph/content/hybrid) |

### Projects

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `project_list` | List all projects with note counts | `response_format` |
| `project_switch` | Switch to a project context | `project_name`\* |
| `project_create` | Create a new project | `project_name`\* |

### Sessions

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `session_observe` | Log an event to a session | `session_id`\*, `event_type`\*, `content`\*, `metadata` |
| `session_summary` | Generate AI summary of a session | `session_id`\* |
| `session_context` | Get session events and summary | `session_id`\*, `include_events`, `include_summary` |

### Profile & Recall

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `get_profile` | Get user/project profile | `project`\* |
| `recall` | Search memories + profile summary | `query`\*, `containerTag`, `includeProfile` |

\* = required parameter

### memory:// URI Patterns (for `build_context`)

```
memory://note/123          — Note by ID
memory://search/auth       — Search for "auth"
memory://tags/security     — Notes tagged "security"
memory://project/api       — Notes in project "api"
memory://path/docs/arch    — Note by relative path
```

### Note Types

`note` | `decision` | `error` | `knowledge` | `pattern` | `session` | `research`

### Search Sort Options

`relevance` | `created_desc` | `created_asc` | `updated_desc` | `updated_asc` | `title_asc`

## Troubleshooting

**"Server not connected"** after `/mcp`:
- Verify `bun` is installed: `which bun`
- Check `cwd` path exists and contains `src/index.ts`
- Run `bun install` in the mcp-server directory
- Check the API URL is reachable: `curl http://localhost:8000/api/health`

**Tools timeout or return errors**:
- Verify the backend API is running (Docker: `docker ps | grep memory`)
- Check API URL in env var matches running backend
- Look at MCP server logs: restart Claude Code with `--mcp-debug`

**Permission denied for tools**:
- Add tools to `allowedTools` in `.claude/settings.json`
- Or approve individually when prompted
