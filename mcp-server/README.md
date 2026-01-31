# Obsidian-Memory MCP Server

MCP (Model Context Protocol) server for Obsidian-Memory, providing memory management tools for Claude Code.

## Features

- **Memory Tools**: Read, write, search, and supersede notes
- **Graph Tools**: Traverse knowledge graph and find similar notes
- **Project Tools**: Manage projects and switch contexts
- **Session Tools**: Track sessions, observe events, and generate summaries
- **Context Building**: Build context from memory:// URIs

## Architecture

The MCP server supports two transport modes:

1. **Stdio Transport**: For local CLI usage (Claude Code)
2. **SSE Transport**: For HTTP/remote access (Claude.ai)

Both transports share the same tool handlers and provide identical functionality.

## Installation

```bash
bun install
```

## Usage

### Stdio Transport (Default - for Claude Code CLI)

```bash
bun run src/index.ts
```

Or set explicitly:
```bash
MCP_TRANSPORT=stdio bun run src/index.ts
```

### SSE Transport (for Claude.ai / Remote Access)

Start the server with SSE transport:

```bash
MCP_TRANSPORT=sse MCP_SSE_PORT=3000 bun run src/index.ts
```

The server provides a unified endpoint at `/mcp`:
- `POST /mcp` - Handle JSON-RPC requests (initialize, tools/call, etc.)
- `GET /mcp` - Open SSE stream for server notifications
- `DELETE /mcp` - Terminate session

### Environment Variables

- `MCP_TRANSPORT` - Transport type: `stdio` (default) or `sse`
- `MCP_SSE_PORT` - Port for SSE server (default: 3000)
- `MCP_PATH` - Path for MCP endpoint (default: `/mcp`)
- `BACKEND_URL` - Backend API URL (default: `http://localhost:8000`)

## Development

```bash
# Run in development mode with watch
bun run dev

# Type check
bun run typecheck

# Lint
bun run lint

# Format
bun run format

# Test
bun test
```

## Building

```bash
bun run build
```

## Tools

The server provides 13 MCP tools across 5 categories:

### Memory Tools (4 tools)
- `mem_read` - Read a note by ID, permalink, or search query
- `mem_write` - Create or update a note with metadata
- `mem_search` - Search notes with filters (tags, project, type, FTS5)
- `mem_supersede` - Mark a note as superseded by another (creates bi-directional relationship)

### Graph Tools (2 tools)
- `graph_traverse` - Traverse the knowledge graph using BFS/DFS
- `graph_similar` - Find similar notes using graph/content/hybrid methods

### Project Tools (3 tools)
- `project_list` - List all projects with note counts
- `project_switch` - Switch to a project context and view recent notes
- `project_create` - Create a new project with validation

### Session Tools (3 tools)
- `session_observe` - Add observations/events to a session
- `session_summary` - Generate AI summary of session events
- `session_context` - Get session context with events and summary

### Context Tools (1 tool)
- `build_context` - Build context from memory:// URI patterns

## Testing

The MCP server includes comprehensive test coverage:

```bash
# Run all tests
bun test

# Run specific test suites
bun test memory.test.ts       # Memory tools tests
bun test graph.test.ts        # Graph tools tests
bun test project.test.ts      # Project tools tests
bun test session.test.ts      # Session tools tests
bun test context.test.ts      # Context tool tests
bun test stdio-integration    # Stdio transport tests
bun test sse-integration      # SSE transport tests
bun test end-to-end          # Complete E2E tests

# Run with coverage
bun test --coverage
```

## Configuration Examples

### For Claude Code (.mcp.json)

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "command": "bun",
      "args": ["run", "/path/to/mcp-server/src/index.ts"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "BACKEND_URL": "http://localhost:8000"
      }
    }
  }
}
```

### For Claude.ai (with SSE transport)

```json
{
  "mcpServers": {
    "obsidian-memory": {
      "url": "http://localhost:3000/mcp",
      "transport": "sse"
    }
  }
}
```

## API Response Formats

All tools support two response formats:
- `json` - Structured JSON data (default)
- `markdown` - Human-readable Markdown text

Example:
```javascript
// JSON format
await mem_read({ id: 1, response_format: 'json' })

// Markdown format
await mem_read({ id: 1, response_format: 'markdown' })
```
