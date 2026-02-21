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
      "cwd": "/path/to/Obsidian-Memory/mcp-server",
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
      "cwd": "/path/to/Obsidian-Memory/mcp-server",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OBSIDIAN_MEMORY_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Option 3: Remote via Docker (No Local Install)

If the MCP server is running in Docker (e.g., `memory.example.com`), point to the API URL:

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "bun",
      "args": ["run", "src/index.ts"],
      "cwd": "/path/to/Obsidian-Memory/mcp-server",
      "env": {
        "MCP_TRANSPORT": "stdio",
        "OBSIDIAN_MEMORY_API_URL": "https://memory.example.com/api"
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

## Automatic Session Tracking (Hooks)

Obsidian-Memory includes **10 Claude Code hooks** that automatically track your session without any MCP tool calls. This saves tokens and provides comprehensive session logging with zero effort.

### What Gets Tracked Automatically

| Event | Hook | Description |
|-------|------|-------------|
| Session start | `SessionStart` | Creates session, sets env vars via `CLAUDE_ENV_FILE` |
| User prompts | `UserPromptSubmit` | Logs each prompt (truncated to 500 chars) |
| Bash validation | `PreToolUse:Bash` | Blocks commands accessing `.env`, `.git/`, `node_modules`, etc. |
| File edits | `PostToolUse:Write\|Edit` | Logs every file write/edit with path |
| Searches | `PostToolUse:Grep\|Glob\|WebSearch\|WebFetch` | Logs search queries and patterns |
| Tool failures | `PostToolUseFailure` | Logs tool errors (skips user interrupts) |
| Subagent spawns | `SubagentStart` | Logs when subagents are dispatched |
| Context compaction | `PreCompact` | Triggers AI session summary before context loss |
| Claude stops | `Stop` | Ensures session summary exists |
| Session end | `SessionEnd` | Ends session with auto-summarization |

### How It Works

1. On `SessionStart`, the hook creates a session via the backend API and writes `OBSIDIAN_MEMORY_SESSION_ID` to `$CLAUDE_ENV_FILE`
2. All subsequent hooks read this env var to log observations
3. Async hooks (6 of 10) fire in the background — zero blocking, zero token cost
4. If the backend is down, all hooks silently exit 0 (fail-open)

### Hook Files

Located in `.claude/hooks/` (configured in `.claude/settings.json`):

```
.claude/hooks/
├── _lib.sh                    # Shared library (API calls, JSON parsing)
├── session-start.sh           # sync, 10s timeout
├── user-prompt-submit.sh      # async, 5s timeout
├── pre-tool-use-bash.sh       # sync, 5s timeout
├── post-tool-use-edits.sh     # async, 5s timeout
├── post-tool-use-search.sh    # async, 5s timeout
├── post-tool-failure.sh       # async, 5s timeout
├── subagent-start.sh          # async, 5s timeout
├── pre-compact.sh             # sync, 30s timeout
├── stop.sh                    # sync, 10s timeout
└── session-end.sh             # async, 30s timeout
```

### What You Still Need MCP Tools For

The hooks handle all session tracking. You still use MCP tools for:
- **Reading/writing notes**: `mem_read`, `mem_write`, `mem_search`, `mem_delete`
- **Knowledge graph**: `graph_traverse`, `graph_similar`, `build_context`
- **Recall/profiles**: `recall`, `get_profile`
- **Project management**: `project_list`, `project_switch`

## CLAUDE.md Integration

Add to your project's `CLAUDE.md` for automatic context:

```markdown
## Obsidian-Memory Integration

This project uses Obsidian-Memory for persistent knowledge management.
Session tracking is fully automatic via hooks — no manual session_observe calls needed.

### Usage Patterns
- **Before starting work**: Use `recall` to check for relevant past context
- **Search first**: Use `mem_search` before answering questions about past decisions
- **Log decisions**: Use `mem_write` to record architectural decisions and patterns
- **Build context**: Use `build_context` with memory:// URIs to gather related notes

### Memory-Aware Workflow
1. `recall` or `mem_search` for existing knowledge
2. Work on the task
3. `mem_write` important decisions/patterns/solutions
4. Session tracking happens automatically via hooks
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
